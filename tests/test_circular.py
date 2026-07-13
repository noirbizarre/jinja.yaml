"""Tests for circular reference detection."""

from __future__ import annotations

import pytest

from jinja_yaml import load_dict
from jinja_yaml.exceptions import CircularReferenceError


def test_direct_two_key_cycle() -> None:
    with pytest.raises(CircularReferenceError) as excinfo:
        load_dict({"a": "{{ b }}", "b": "{{ a }}"})
    assert excinfo.value.path[0] == excinfo.value.path[-1]


def test_three_key_cycle_reports_path() -> None:
    with pytest.raises(CircularReferenceError) as excinfo:
        load_dict({"a": "{{ b }}", "b": "{{ c }}", "c": "{{ a }}"})
    assert str(excinfo.value) == "Circular reference detected: a -> b -> c -> a"


def test_self_reference_cycle() -> None:
    with pytest.raises(CircularReferenceError) as excinfo:
        load_dict({"a": "{{ a }}"})
    assert excinfo.value.path == [("a",), ("a",)]


def test_cycle_through_nested_structure() -> None:
    document = {
        "a": {"ref": "{{ b }}"},
        "b": "{{ a.ref }}",
    }
    with pytest.raises(CircularReferenceError):
        load_dict(document)
