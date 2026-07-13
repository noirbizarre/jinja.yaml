"""Tests for the merging phase."""

from __future__ import annotations

import pytest

from jinja_yaml.exceptions import DuplicateKeyError
from jinja_yaml.merger import merge


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
