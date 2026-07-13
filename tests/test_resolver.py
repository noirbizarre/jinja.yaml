"""Tests for the resolution phase."""

from __future__ import annotations

import pytest

from jinja_yaml import load_dict
from jinja_yaml.environment import Environment
from jinja_yaml.exceptions import InvalidTemplateError, ResolutionError


def test_basic_reference() -> None:
    assert load_dict({"fqdn": "nas.{{ domain }}", "domain": "home.arpa"}) == {
        "fqdn": "nas.home.arpa",
        "domain": "home.arpa",
    }


def test_declaration_order_independence() -> None:
    forward = load_dict({"fqdn": "nas.{{ domain }}", "domain": "home.arpa"})
    backward = load_dict({"domain": "home.arpa", "fqdn": "nas.{{ domain }}"})
    assert forward == backward


def test_chained_references() -> None:
    assert load_dict({"a": "{{ b }}", "b": "{{ c }}", "c": "value"}) == {
        "a": "value",
        "b": "value",
        "c": "value",
    }


def test_nested_dict_reference() -> None:
    document = {"net": {"host": "{{ domain }}"}, "domain": "home.arpa"}
    assert load_dict(document) == {"net": {"host": "home.arpa"}, "domain": "home.arpa"}


def test_dotted_reference_into_nested_dict() -> None:
    document = {"url": "https://{{ net.domain }}", "net": {"domain": "home.arpa"}}
    assert load_dict(document)["url"] == "https://home.arpa"


def test_nested_list_reference() -> None:
    document = {"hosts": ["{{ domain }}", "www.{{ domain }}"], "domain": "home.arpa"}
    assert load_dict(document)["hosts"] == ["home.arpa", "www.home.arpa"]


def test_native_int_is_preserved() -> None:
    result = load_dict({"port": "{{ base }}", "base": 8080})
    assert result["port"] == 8080
    assert isinstance(result["port"], int)


def test_native_list_is_preserved() -> None:
    result = load_dict({"ref": "{{ items }}", "items": [1, 2, 3]})
    assert result["ref"] == [1, 2, 3]


def test_native_dict_is_preserved() -> None:
    result = load_dict({"ref": "{{ cfg }}", "cfg": {"a": 1}})
    assert result["ref"] == {"a": 1}


def test_string_interpolation_coerces_to_string() -> None:
    result = load_dict({"label": "port-{{ port }}", "port": 8080})
    assert result["label"] == "port-8080"


def test_deeply_nested_structure() -> None:
    document = {
        "root": {"level1": {"level2": [{"value": "{{ answer }}"}]}},
        "answer": 42,
    }
    result = load_dict(document)
    assert result == {
        "root": {"level1": {"level2": [{"value": 42}]}},
        "answer": 42,
    }


def test_missing_reference_raises() -> None:
    with pytest.raises(ResolutionError, match="undefined key or namespace 'missing'"):
        load_dict({"x": "{{ missing }}"})


def test_invalid_template_raises() -> None:
    with pytest.raises(InvalidTemplateError):
        load_dict({"x": "{{ oops"})


def test_missing_nested_attribute_raises_at_render() -> None:
    with pytest.raises(ResolutionError):
        load_dict({"x": "prefix-{{ data.missing }}"}, namespaces={"data": {"present": 1}})


def test_non_templated_values_pass_through() -> None:
    document = {"a": 1, "b": 1.5, "c": True, "d": None, "e": "plain"}
    assert load_dict(document) == document


def test_caching_resolves_each_node_once() -> None:
    calls: list[str] = []

    def track(value: str) -> str:
        calls.append(value)
        return value

    env = Environment(filters={"track": track})
    document = {
        "seed": "x",
        "base": "{{ seed | track }}",
        "a": "{{ base }}",
        "b": "{{ base }}",
        "c": "{{ base }}",
    }
    load_dict(document, environment=env)
    assert calls == ["x"]
