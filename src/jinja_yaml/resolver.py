"""Resolution phase: evaluate templated values against the merged document.

The resolver ties the other modules together:

1. Walk the merged tree, collecting every templated leaf and its key path.
2. Statically discover, for each leaf, the top-level keys it references and
   record the corresponding edges in a :class:`~jinja_yaml.graph.DependencyGraph`.
3. Detect cycles up-front and raise :class:`CircularReferenceError`.
4. Resolve values lazily, caching each resolved node, and rendering through the
   :class:`~jinja_yaml.environment.Environment` so single-expression templates
   keep their native type.

A runtime resolution stack is maintained as a defensive net: it catches cycles
introduced by custom filters, globals or functions that static analysis cannot
see.
"""

from __future__ import annotations

from typing import Any, cast

from jinja2 import TemplateSyntaxError, UndefinedError

from .environment import Environment
from .exceptions import (
    CircularReferenceError,
    InvalidTemplateError,
    NamespaceCollisionError,
    ResolutionError,
)
from .graph import DependencyGraph
from .types import Document, KeyPath, MappingClass, Namespaces, Node, format_key_path

__all__ = ["resolve"]


def resolve(
    document: Document,
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
    mapping_cls: MappingClass = dict,
) -> Document:
    """Resolve every templated value in ``document`` and return a new document.

    Resolved mappings are built with ``mapping_cls``, which defaults to
    :class:`dict`. Pass any :class:`~collections.abc.MutableMapping` subclass to
    control the concrete type of the returned document and its nested mappings.
    """
    namespaces = namespaces or {}
    environment = environment or Environment()
    _check_namespace_collisions(document, namespaces)
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
        document: Document,
        namespaces: Namespaces,
        environment: Environment,
        mapping_cls: MappingClass,
    ) -> None:
        self._document = document
        self._namespaces = namespaces
        self._env = environment
        self._mapping_cls = mapping_cls
        self._cache: dict[KeyPath, Node] = {}
        self._stack: list[KeyPath] = []
        self._graph = DependencyGraph()

    def run(self) -> Document:
        self._build_graph(self._document, path=())
        cycle = self._graph.find_cycle()
        if cycle is not None:
            raise CircularReferenceError(cycle)
        resolved = self._mapping_cls()
        for key, value in self._document.items():
            resolved[key] = self._resolve_node(value, (key,))
        return cast("Document", resolved)

    # -- dependency graph -------------------------------------------------

    def _build_graph(self, node: Node, *, path: KeyPath) -> None:
        if isinstance(node, str) and self._env.is_template(node):
            self._graph.add_node(path)
            for name in self._referenced_variables(node, path):
                if name in self._document:
                    self._graph.add_edge(path, (name,))
        elif isinstance(node, dict):
            for key, value in node.items():
                self._build_graph(value, path=(*path, key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self._build_graph(value, path=(*path, index))

    def _referenced_variables(self, source: str, path: KeyPath) -> set[str]:
        try:
            return self._env.referenced_variables(source)
        except TemplateSyntaxError as error:
            raise InvalidTemplateError(path, error.message or str(error)) from error

    # -- resolution -------------------------------------------------------

    def _resolve_node(self, node: Node, path: KeyPath) -> Node:
        if path in self._cache:
            return self._cache[path]
        if path in self._stack:
            cycle = [*self._stack[self._stack.index(path) :], path]
            raise CircularReferenceError(cycle)

        self._stack.append(path)
        try:
            resolved = self._resolve_value(node, path)
        finally:
            self._stack.pop()

        self._cache[path] = resolved
        return resolved

    def _resolve_value(self, node: Node, path: KeyPath) -> Node:
        if isinstance(node, str) and self._env.is_template(node):
            return self._render(node, path)
        if isinstance(node, dict):
            result = self._mapping_cls()
            for key, value in node.items():
                result[key] = self._resolve_node(value, (*path, key))
            return cast("Node", result)
        if isinstance(node, list):
            return [self._resolve_node(value, (*path, index)) for index, value in enumerate(node)]
        return node

    def _render(self, source: str, path: KeyPath) -> Node:
        # Syntax is validated up-front in ``_build_context`` via static parsing,
        # so only render-time (undefined) failures can surface here.
        context = self._build_context(source, path)
        try:
            template = self._env.from_string(source)
            return template.render(context)
        except UndefinedError as error:
            raise ResolutionError(
                f"Failed to resolve {format_key_path(path)!r}: {error}"
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
            elif name not in self._namespaces:
                raise ResolutionError(
                    f"Failed to resolve {format_key_path(path)!r}: "
                    f"reference to undefined key or namespace {name!r}"
                )
        return context
