"""Resolution phase: evaluate templated values against the merged document.

The resolver ties the other modules together:

1. Walk the merged tree, recording value paths and container dependencies.
2. Statically discover, for each leaf, the top-level keys it references and
   record the corresponding edges in a :class:`~jinja_yaml.graph.DependencyGraph`,
   including requirements from statically referenced loader templates.
3. Detect cycles up-front and raise :class:`CircularReferenceError`.
4. Resolve values lazily, caching each resolved node, and rendering through the
   :class:`~jinja_yaml.environment.Environment` for native Python results,
   including conversion of literal-looking rendered strings.

A runtime resolution stack is maintained as a defensive net: it catches cycles
introduced by custom filters, globals or functions that static analysis cannot
see.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, overload

from jinja2 import TemplateError, TemplateSyntaxError, Undefined, UndefinedError

from .environment import Environment
from .exceptions import (
    CircularReferenceError,
    InvalidTemplateError,
    MissingReferenceError,
    NamespaceCollisionError,
    ResolutionError,
    SourceLocation,
    TemplateEvaluationError,
)
from .graph import DependencyGraph
from .provenance import _annotate_resolution, _Provenance, _SourceDocument
from .types import Document, KeyPath, MappingClass, Namespaces, Node, ResolvedDocument

__all__ = ["resolve"]


@overload
def resolve(
    document: Document,
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
) -> dict[str, Any]: ...


@overload
def resolve[M: MutableMapping[str, Any]](
    document: Document,
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
    mapping_cls: type[M],
) -> M: ...


def resolve(
    document: Document,
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
    mapping_cls: MappingClass = dict,
) -> ResolvedDocument:
    """Resolve every templated value in ``document`` and return a new document.

    Structural document mappings are built with ``mapping_cls``, which defaults
    to :class:`dict`. Pass a zero-argument :class:`~collections.abc.MutableMapping`
    subclass to customize them. Mappings produced by template evaluation retain
    their native type and identity instead of being converted.
    """
    return _resolve(
        _SourceDocument(document),
        namespaces=namespaces,
        environment=environment,
        mapping_cls=mapping_cls,
    ).data


def _resolve(
    document: _SourceDocument[Document],
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
    mapping_cls: MappingClass = dict,
) -> _SourceDocument[ResolvedDocument]:
    namespaces = namespaces or {}
    environment = environment or Environment()
    _check_namespace_collisions(document.data, namespaces)
    resolver = _Resolver(document, namespaces, environment, mapping_cls)
    return resolver.run()


def _check_namespace_collisions(document: Document, namespaces: Namespaces) -> None:
    for name in namespaces:
        if name in document:
            raise NamespaceCollisionError(name)


class _Resolver:
    """Stateful helper performing a single resolution pass with caching."""

    def __init__(
        self,
        document: _SourceDocument[Document],
        namespaces: Namespaces,
        environment: Environment,
        mapping_cls: MappingClass,
    ) -> None:
        self._document = document.data
        self._origins = document.origins
        self._resolved_origins: _Provenance = {}
        self._namespaces = namespaces
        self._env = environment
        self._mapping_cls = mapping_cls
        self._cache: dict[KeyPath, Any] = {}
        self._stack: list[KeyPath] = []
        self._graph = DependencyGraph()
        self._references: dict[KeyPath, tuple[str, ...]] = {}

    def _error(self, error: ResolutionError) -> ResolutionError:
        locations = self._origins.get(error.key_path, ()) if error.key_path is not None else ()
        return _annotate_resolution(error, locations)

    def run(self) -> _SourceDocument[ResolvedDocument]:
        self._build_graph(self._document, path=())
        cycle = self._graph.find_cycle()
        if cycle is not None:
            raise self._error(CircularReferenceError(cycle))
        resolved = self._mapping_cls()
        for key, value in self._document.items():
            resolved[key] = self._resolve_node(value, (key,))
        if () in self._origins:
            self._resolved_origins[()] = self._origins[()]
        return _SourceDocument(resolved, self._resolved_origins)

    # -- dependency graph -------------------------------------------------

    def _build_graph(self, node: Node, *, path: KeyPath) -> None:
        if path:
            self._graph.add_node(path)
        if isinstance(node, str) and self._env.is_template(node):
            for name in self._referenced_variables(node, path):
                if name in self._document:
                    self._graph.add_edge(path, (name,))
        elif isinstance(node, dict):
            for key, value in node.items():
                if path:
                    self._graph.add_edge(path, (*path, key))
                self._build_graph(value, path=(*path, key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self._graph.add_edge(path, (*path, index))
                self._build_graph(value, path=(*path, index))

    def _referenced_variables(self, source: str, path: KeyPath) -> tuple[str, ...]:
        if path in self._references:
            return self._references[path]
        try:
            references = tuple(sorted(self._env.referenced_variables(source)))
        except TemplateSyntaxError as error:
            template = f" in template {error.name!r}" if error.name else ""
            raise self._error(
                InvalidTemplateError(
                    path,
                    f"{error}{template}",
                    location=SourceLocation(error.filename or error.name, error.lineno),
                )
            ) from error
        except (TemplateError, TypeError) as error:
            raise self._error(
                InvalidTemplateError(path, f"Failed to analyze template: {error}")
            ) from error
        self._references[path] = references
        return references

    # -- resolution -------------------------------------------------------

    def _resolve_node(self, node: Node, path: KeyPath) -> Any:
        if path in self._cache:
            return self._cache[path]
        if path in self._stack:
            cycle = [*self._stack[self._stack.index(path) :], path]
            raise self._error(CircularReferenceError(cycle))

        self._stack.append(path)
        try:
            resolved = self._resolve_value(node, path)
        finally:
            self._stack.pop()

        self._cache[path] = resolved
        if path in self._origins:
            self._resolved_origins[path] = self._origins[path]
        return resolved

    def _resolve_value(self, node: Node, path: KeyPath) -> Any:
        if isinstance(node, str) and self._env.is_template(node):
            result = self._render(node, path)
            if locations := self._origins.get(path):
                self._record_produced_origins(result, path, locations)
            return result
        if isinstance(node, dict):
            result = self._mapping_cls()
            for key, value in node.items():
                result[key] = self._resolve_node(value, (*path, key))
            return result
        if isinstance(node, list):
            return [self._resolve_node(value, (*path, index)) for index, value in enumerate(node)]
        return node

    def _record_produced_origins(
        self,
        node: Any,
        path: KeyPath,
        locations: tuple[SourceLocation, ...],
    ) -> None:
        """Generated descendants belong to the template, not its dependencies."""
        active: set[int] = set()
        pending: list[tuple[Any, KeyPath, bool]] = [(node, path, False)]
        while pending:
            node, path, leaving = pending.pop()
            if leaving:
                active.remove(id(node))
                continue
            self._resolved_origins[path] = locations
            if id(node) in active:
                continue
            if isinstance(node, (Mapping, list)):
                active.add(id(node))
                pending.append((node, path, True))
                children = node.items() if isinstance(node, Mapping) else enumerate(node)
                pending.extend((value, (*path, key), False) for key, value in children)

    def _render(self, source: str, path: KeyPath) -> Any:
        # Static sources were validated during graph construction. Dynamic
        # loader targets can still fail at render time.
        context = self._build_context(source, path)
        try:
            template = self._env.from_string(source)
            result = template.render(context)
            _check_defined(result)
            return result
        except ResolutionError:
            # Preserve domain errors raised by caller-provided extensions.
            raise
        except UndefinedError as error:
            raise self._error(
                MissingReferenceError(path, message=str(error), dependency_chain=tuple(self._stack))
            ) from error
        except TemplateSyntaxError as error:
            raise self._error(
                InvalidTemplateError(
                    path,
                    str(error),
                    dependency_chain=tuple(self._stack),
                    location=SourceLocation(error.filename or error.name, error.lineno),
                )
            ) from error
        except Exception as error:
            # Jinja lets Python errors from operators, filters and globals escape.
            raise self._error(
                TemplateEvaluationError(
                    path,
                    f"Evaluation failed ({type(error).__name__}): {error}",
                    dependency_chain=tuple(self._stack),
                )
            ) from error

    def _build_context(self, source: str, path: KeyPath) -> dict[str, Any]:
        """Resolve exactly the dependencies a template needs, then expose them.

        Any referenced root variable that matches neither a document key nor an
        injected namespace is a missing reference and fails loudly. This is
        needed because a native, single-expression template renders an
        undefined value without triggering Jinja's ``StrictUndefined`` guard.
        """
        context: dict[str, Any] = dict(self._namespaces)
        for name in self._referenced_variables(source, path):
            if name in self._document:
                context[name] = self._resolve_node(self._document[name], (name,))
            elif name not in self._namespaces and name not in self._env.globals:
                raise self._error(
                    MissingReferenceError(path, name, dependency_chain=tuple(self._stack))
                )
        return context


def _check_defined(result: Any) -> None:
    """Check native containers without copying them or following cycles."""
    pending = [result]
    visited: set[int] = set()
    while pending:
        value = pending.pop()
        if isinstance(value, Undefined):
            # Native rendering need not use the Undefined, even under StrictUndefined.
            raise UndefinedError(str(value) or "Template returned an undefined value")
        if id(value) in visited:
            continue
        if isinstance(value, Mapping):
            visited.add(id(value))
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, (list, tuple, set, frozenset)):
            visited.add(id(value))
            pending.extend(value)
