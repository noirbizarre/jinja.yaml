"""Tests for circular reference detection."""

from __future__ import annotations

import pytest

from jinja_yaml import load_dict
from jinja_yaml.environment import Environment
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


def test_nested_list_cycle_is_detected_before_rendering() -> None:
    rendered = []
    environment = Environment(globals={"record": lambda: rendered.append(True)})
    document = {"first": "{{ record() }}", "a": ["{{ b }}"], "b": "{{ a[0] }}"}
    with pytest.raises(CircularReferenceError) as excinfo:
        load_dict(document, environment=environment)
    assert str(excinfo.value) == "Circular reference detected: a -> a[0] -> b -> a"
    assert rendered == []


def test_sibling_references_still_require_the_whole_root() -> None:
    with pytest.raises(CircularReferenceError):
        load_dict({"settings": {"host": "localhost", "url": "{{ settings.host }}"}})


def test_multiple_references_have_a_stable_cycle_path() -> None:
    with pytest.raises(CircularReferenceError) as excinfo:
        load_dict({"a": "{{ c }} {{ b }}", "b": "{{ a }}", "c": "{{ a }}"})
    assert excinfo.value.path == [("a",), ("b",), ("a",)]
