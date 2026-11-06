"""Tests for the merging phase."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from jinja_yaml.exceptions import DuplicateKeyError
from jinja_yaml.merger import merge
from jinja_yaml.types import Document, MergeStrategy, Node


def test_merge_disjoint_documents() -> None:
    assert merge([{"a": 1}, {"b": 2}]) == {"a": 1, "b": 2}


def test_merge_is_order_independent() -> None:
    forward = merge([{"a": 1}, {"b": 2}])
    backward = merge([{"b": 2}, {"a": 1}])
    assert forward == backward


def test_deep_merge_nested_dicts() -> None:
    merged = merge([{"net": {"domain": "a"}}, {"net": {"host": "b"}}])
    assert merged == {"net": {"domain": "a", "host": "b"}}


def test_identical_leaf_redefinition_is_allowed() -> None:
    assert merge([{"a": 1}, {"a": 1}]) == {"a": 1}


def test_conflicting_leaf_raises() -> None:
    with pytest.raises(DuplicateKeyError) as excinfo:
        merge([{"a": 1}, {"a": 2}])
    assert excinfo.value.path == ("a",)


def test_conflicting_nested_leaf_reports_full_path() -> None:
    with pytest.raises(DuplicateKeyError) as excinfo:
        merge([{"net": {"domain": "a"}}, {"net": {"domain": "b"}}])
    assert excinfo.value.path == ("net", "domain")


def test_list_is_treated_as_leaf() -> None:
    with pytest.raises(DuplicateKeyError):
        merge([{"items": [1]}, {"items": [1, 2]}])


def test_dict_versus_scalar_conflict_raises() -> None:
    with pytest.raises(DuplicateKeyError):
        merge([{"a": {"b": 1}}, {"a": 2}])


def test_merge_single_document_is_identity() -> None:
    assert merge([{"a": {"b": 1}}]) == {"a": {"b": 1}}


@pytest.mark.parametrize("strategy", ["strict", "override"])
def test_merge_empty_and_generator_inputs(strategy: MergeStrategy) -> None:
    assert merge(iter([]), merge_strategy=strategy) == {}
    assert merge(({key: 1} for key in ["a", "b"]), merge_strategy=strategy) == {"a": 1, "b": 1}


def test_nested_override_preserves_siblings_and_uses_source_order() -> None:
    documents: list[Document] = [
        {"net": {"port": 80, "host": "localhost"}},
        {"net": {"port": 8080, "tls": True}},
        {"net": {"port": 443}},
        {"net": {}},
    ]
    assert merge(documents, merge_strategy="override") == {
        "net": {"port": 443, "host": "localhost", "tls": True}
    }
    assert merge(reversed(documents), merge_strategy="override") == {
        "net": {"port": 80, "host": "localhost", "tls": True}
    }


@pytest.mark.parametrize(
    ("earlier", "later"),
    [
        ("old", "new"),
        (1, 2.5),
        (True, False),
        ("old", None),
        (None, "new"),
        ([1, 2], []),
        ([{"x": 1}], [{"y": 2}]),
        ({"old": 1}, 2),
        (2, {"new": 1}),
        ({"old": 1}, [2]),
        ([2], {"new": 1}),
        ([2], "new"),
        ("old", [2]),
    ],
)
def test_override_replaces_atomic_values_and_incompatible_categories(
    earlier: Node, later: Node
) -> None:
    assert merge([{"value": earlier}, {"value": later}], merge_strategy="override") == {
        "value": later
    }
    with pytest.raises(DuplicateKeyError):
        merge([{"value": earlier}, {"value": later}], merge_strategy="strict")


@pytest.mark.parametrize(("earlier", "later"), [(True, 1), (1, 1.0), ([True], [1])])
def test_equal_values_keep_first_in_strict_and_last_in_override(earlier: Node, later: Node) -> None:
    strict = merge([{"value": earlier}, {"value": later}])["value"]
    override = merge([{"value": earlier}, {"value": later}], merge_strategy="override")["value"]
    if isinstance(strict, list) and isinstance(override, list) and isinstance(later, list):
        assert type(strict[0]) is bool
        assert type(override[0]) is type(later[0])
    else:
        assert type(strict) is type(earlier)
        assert type(override) is type(later)


def test_strict_accepts_identical_lists() -> None:
    assert merge([{"items": [{"x": 1}]}, {"items": [{"x": 1}]}]) == {"items": [{"x": 1}]}


def test_override_copies_replacements_and_shared_containers() -> None:
    shared: Node = [{"x": 1}]
    earlier: Document = {"a": {"old": 1}}
    later: Document = {"a": shared, "b": shared}
    result = merge([earlier, later], merge_strategy="override")
    assert earlier == {"a": {"old": 1}}
    assert later == {"a": [{"x": 1}], "b": [{"x": 1}]}
    a, b = result["a"], result["b"]
    assert isinstance(a, list) and isinstance(b, list)
    assert a is not shared and b is not shared and a is not b
    assert a[0] is not b[0]
    assert isinstance(a[0], dict)
    a[0]["x"] = 2
    assert b == shared == [{"x": 1}]


def test_invalid_strategy_does_not_consume_documents() -> None:
    def documents() -> Iterable[Document]:
        pytest.fail("invalid strategy must be rejected before consuming input")
        yield {}

    with pytest.raises(ValueError, match="Unknown merge strategy"):
        merge(documents(), merge_strategy="unknown")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="Unknown merge strategy"):
        merge([], merge_strategy="unknown")  # ty: ignore[invalid-argument-type]
