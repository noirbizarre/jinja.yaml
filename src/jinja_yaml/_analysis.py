"""Scope-aware static analysis of loader-backed Jinja templates.

Only the analysis tree is augmented: synthetic reads at context-sharing sites
let Jinja's own symbol analysis distinguish caller locals from external roots.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import TemplateNotFound, TemplateRuntimeError, meta, nodes
from jinja2.compiler import CodeGenerator, Frame
from jinja2.meta import TrackingCodeGenerator
from jinja2.visitor import NodeTransformer

if TYPE_CHECKING:
    from .environment import Environment


class _ExternalReads(TrackingCodeGenerator):
    """Collect context reads without excluding names that also have globals."""

    def enter_frame(self, frame: Frame) -> None:
        CodeGenerator.enter_frame(self, frame)
        for action, name in frame.symbols.loads.values():
            if action == "resolve":
                self.undeclared_identifiers.add(name)


def _external_reads(tree: nodes.Template, environment: Environment) -> set[str]:
    generator = _ExternalReads(environment)
    generator.visit(tree)
    return generator.undeclared_identifiers


class TemplateAnalysis:
    """Analyze a source and its static template references without rendering."""

    def __init__(self, environment: Environment) -> None:
        self.environment = environment
        self._cache: dict[str, set[str]] = {}
        self._active: list[str] = []

    def variables(
        self, source: str, name: str | None = None, filename: str | None = None
    ) -> set[str]:
        tree = self.environment.parse(source, name=name, filename=filename)
        # Dynamic references yield None; their name expressions are still
        # analyzed normally, but their eventual targets remain runtime-only.
        if not list(meta.find_referenced_templates(tree)):
            return _external_reads(tree, self.environment)
        transformer = _References(self, name)
        # Parsing returns a fresh tree; only variable requirements are cached.
        tree = transformer.visit(tree)
        # Parent roots run after the child's top-level assignments, not at the
        # textual position of the extends tag.
        tree.body.extend(_reads(transformer.parent_variables, tree.lineno))
        return _external_reads(tree, self.environment)

    def referenced(self, names: list[str], parent: str | None, *, ignore: bool) -> set[str]:
        loader = self.environment.loader
        if loader is None:
            raise TemplateRuntimeError(f"Cannot analyze templates {names!r}: no loader configured")
        for name in names:
            resolved_name = self.environment.join_path(name, parent) if parent is not None else name
            if resolved_name in self._active:
                chain = " -> ".join([*self._active, resolved_name])
                raise TemplateRuntimeError(f"Recursive static template reference: {chain}")
            if resolved_name not in self._cache:
                try:
                    source, filename, _ = loader.get_source(self.environment, resolved_name)
                except TemplateNotFound:
                    continue
                except RuntimeError as error:
                    raise TemplateRuntimeError(
                        f"Cannot read source for template {resolved_name!r}: {error}"
                    ) from error
                self._active.append(resolved_name)
                try:
                    self._cache[resolved_name] = self.variables(source, resolved_name, filename)
                finally:
                    self._active.pop()
            return self._cache[resolved_name]
        if ignore:
            return set()
        raise TemplateNotFound(", ".join(names))


def _reads(names: set[str], lineno: int) -> list[nodes.Output]:
    reads = []
    for name in sorted(names):
        read = nodes.Output([nodes.Name(name, "load")])
        read.set_lineno(lineno)
        reads.append(read)
    return reads


class _References(NodeTransformer):
    def __init__(self, analysis: TemplateAnalysis, parent: str | None) -> None:
        self.analysis = analysis
        self.parent = parent
        self.parent_variables: set[str] = set()

    def _reference(
        self, node: nodes.Include | nodes.Import | nodes.FromImport | nodes.Extends
    ) -> nodes.Stmt | list[nodes.Stmt]:
        expression = node.template
        names = list(meta.find_referenced_templates(nodes.Template([node])))
        # Keep the entire dynamic construct for ordinary undeclared-variable
        # analysis. A mixed fallback list cannot be selected statically either.
        if None in names or not names:
            return node
        static_names = [name for name in names if name is not None]
        variables = self.analysis.referenced(
            static_names,
            self.parent,
            ignore=isinstance(node, nodes.Include) and node.ignore_missing,
        )
        if isinstance(node, nodes.Extends):
            self.parent_variables.update(variables)
        elif node.with_context:
            return [*_reads(variables, expression.lineno), node]
        return node

    visit_Include = _reference
    visit_Import = _reference
    visit_FromImport = _reference
    visit_Extends = _reference
