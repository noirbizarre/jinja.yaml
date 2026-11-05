"""A small, generic directed dependency graph.

The graph is deliberately independent of Jinja and YAML: it only knows about
nodes and the edges between them. The resolver uses it to reason about the
dependencies between templated values, to detect cycles up-front and to expose
the offending path when a cycle is found.

Nodes are :data:`~jinja_yaml.types.KeyPath` tuples, which are hashable and map
directly onto document locations.
"""

from __future__ import annotations

from graphlib import CycleError, TopologicalSorter

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
        try:
            TopologicalSorter(self._edges).prepare()
        except CycleError as error:
            # graphlib follows successors; our public paths follow dependencies.
            cycle = list(reversed(error.args[1][:-1]))
            positions = {node: index for index, node in enumerate(self._edges)}
            start = min(range(len(cycle)), key=lambda index: positions[cycle[index]])
            cycle = cycle[start:] + cycle[:start]
            return [*cycle, cycle[0]]
        return None

    def static_order(self) -> tuple[KeyPath, ...]:
        """Return dependency-first order; raise ``CycleError`` for a cycle."""
        return tuple(TopologicalSorter(self._edges).static_order())
