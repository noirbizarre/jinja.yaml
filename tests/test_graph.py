"""Unit tests for the generic dependency graph."""

from __future__ import annotations

from jinja_yaml.graph import DependencyGraph


def test_add_node_without_edges() -> None:
    graph = DependencyGraph()
    graph.add_node(("a",))
    assert graph.dependencies(("a",)) == []


def test_add_edge_registers_both_nodes() -> None:
    graph = DependencyGraph()
    graph.add_edge(("a",), ("b",))
    assert graph.dependencies(("a",)) == [("b",)]
    assert graph.dependencies(("b",)) == []


def test_duplicate_edges_are_deduplicated() -> None:
    graph = DependencyGraph()
    graph.add_edge(("a",), ("b",))
    graph.add_edge(("a",), ("b",))
    assert graph.dependencies(("a",)) == [("b",)]


def test_acyclic_graph_has_no_cycle() -> None:
    graph = DependencyGraph()
    graph.add_edge(("a",), ("b",))
    graph.add_edge(("b",), ("c",))
    assert graph.find_cycle() is None


def test_direct_cycle_is_detected() -> None:
    graph = DependencyGraph()
    graph.add_edge(("a",), ("b",))
    graph.add_edge(("b",), ("a",))
    cycle = graph.find_cycle()
    assert cycle is not None
    assert cycle[0] == cycle[-1]


def test_self_cycle_is_detected() -> None:
    graph = DependencyGraph()
    graph.add_edge(("a",), ("a",))
    assert graph.find_cycle() == [("a",), ("a",)]


def test_cycle_path_is_closed() -> None:
    graph = DependencyGraph()
    graph.add_edge(("a",), ("b",))
    graph.add_edge(("b",), ("c",))
    graph.add_edge(("c",), ("a",))
    cycle = graph.find_cycle()
    assert cycle == [("a",), ("b",), ("c",), ("a",)]
