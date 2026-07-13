"""A small, generic directed dependency graph.

The graph is deliberately independent of Jinja and YAML: it only knows about
nodes and the edges between them. The resolver uses it to reason about the
dependencies between templated values, to detect cycles up-front and to expose
the offending path when a cycle is found.

Nodes are :data:`~jinja_yaml.types.KeyPath` tuples, which are hashable and map
directly onto document locations.
"""

from __future__ import annotations

from .types import KeyPath

__all__ = ["DependencyGraph"]


class DependencyGraph:
    """A directed graph of dependencies between key paths.

    An edge ``a -> b`` means "``a`` depends on ``b``" (``a`` must be resolved
    after ``b``).
    """

    def __init__(self) -> None:
        self._edges: dict[KeyPath, list[KeyPath]] = {}

    def add_node(self, node: KeyPath) -> None:
        """Register a node, even if it has no dependencies."""
        self._edges.setdefault(node, [])

    def add_edge(self, dependent: KeyPath, dependency: KeyPath) -> None:
        """Record that ``dependent`` depends on ``dependency``."""
        edges = self._edges.setdefault(dependent, [])
        self.add_node(dependency)
        if dependency not in edges:
            edges.append(dependency)

    def dependencies(self, node: KeyPath) -> list[KeyPath]:
        """Return the direct dependencies of ``node``."""
        return list(self._edges.get(node, []))

    def find_cycle(self) -> list[KeyPath] | None:
        """Return a cycle as an ordered path, or ``None`` if the graph is acyclic.

        The returned path is closed, i.e. its first and last elements are equal,
        so it renders naturally as ``a -> b -> c -> a``.
        """
        visited: set[KeyPath] = set()
        stack: list[KeyPath] = []
        on_stack: set[KeyPath] = set()

        def visit(node: KeyPath) -> list[KeyPath] | None:
            visited.add(node)
            stack.append(node)
            on_stack.add(node)
            for dependency in self._edges.get(node, []):
                if dependency in on_stack:
                    start = stack.index(dependency)
                    return [*stack[start:], dependency]
                if dependency not in visited:
                    cycle = visit(dependency)
                    if cycle is not None:
                        return cycle
            stack.pop()
            on_stack.discard(node)
            return None

        for node in self._edges:
            if node not in visited:
                cycle = visit(node)
                if cycle is not None:
                    return cycle
        return None
