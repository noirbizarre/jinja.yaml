"""Tests for the configurable Jinja environment."""

from __future__ import annotations

import pytest

from jinja_yaml import load_dict
from jinja_yaml.environment import Environment
from jinja_yaml.exceptions import CircularReferenceError, InvalidTemplateError, ResolutionError


def test_custom_filter() -> None:
    env = Environment(filters={"shout": str.upper})
    assert load_dict({"x": "{{ 'hi' | shout }}"}, environment=env)["x"] == "HI"


def test_custom_test() -> None:
    env = Environment(tests={"even": lambda n: n % 2 == 0})
    result = load_dict({"x": "{{ 4 is even }}"}, environment=env)
    assert result["x"] is True


def test_custom_global() -> None:
    env = Environment(globals={"answer": 42})
    assert load_dict({"x": "{{ answer }}"}, environment=env)["x"] == 42


def test_custom_function_global() -> None:
    env = Environment(globals={"double": lambda n: n * 2})
    assert load_dict({"x": "{{ double(21) }}"}, environment=env)["x"] == 42


def test_is_template_detection() -> None:
    env = Environment()
    assert env.is_template("{{ x }}")
    assert env.is_template("{% if x %}y{% endif %}")
    assert not env.is_template("plain string")


def test_referenced_variables_static_analysis() -> None:
    env = Environment()
    assert env.referenced_variables("{{ a }} and {{ b.c }}") == {"a", "b"}


def test_strict_undefined_is_default() -> None:
    with pytest.raises(ResolutionError):
        load_dict({"x": "prefix-{{ missing }}"})


@pytest.mark.parametrize("name", ["answer", "range"])
def test_document_shadows_globals_and_tracks_dependencies(name: str) -> None:
    env = Environment(globals={"answer": 7})
    before = dict(env.globals)
    result = load_dict(
        {"result": "{{ " + name + " }}", name: "{{ base }}", "base": 42}, environment=env
    )
    assert result["result"] == 42
    assert env.globals == before
    with pytest.raises(CircularReferenceError):
        load_dict({"result": "{{ " + name + " }}", name: "{{ result }}"}, environment=env)


def test_namespace_shadows_global() -> None:
    env = Environment(globals={"answer": 7})
    assert load_dict({"result": "{{ answer }}"}, namespaces={"answer": 42}, environment=env) == {
        "result": 42
    }


def test_global_names_respect_local_scope_and_loader_context() -> None:
    from jinja2 import DictLoader

    env = Environment(globals={"answer": 7}, loader=DictLoader({"value": "{{ answer }}"}))
    assert env.referenced_variables("{% set answer = 3 %}{{ answer }}") == set()
    result = load_dict(
        {
            "answer": 42,
            "shared": '{% include "value" %}',
            "isolated": '{% include "value" without context %}',
            "local": '{% set answer = 3 %}{% include "value" %}',
        },
        environment=env,
    )
    assert result == {"answer": 42, "shared": 42, "isolated": 7, "local": 3}


def test_custom_delimiters_render_and_track_dependencies() -> None:
    env = Environment(
        variable_start_string="[[",
        variable_end_string="]]",
        block_start_string="[%",
        block_end_string="%]",
        comment_start_string="[#",
        comment_end_string="#]",
    )
    result = load_dict(
        {
            "copy": "[[ base ]]",
            "block": "[% if base %][[ base ]][% endif %]",
            "comment": "[# ignored #]42",
            "literal": "{{ base }} {% invalid %} {# comment #}",
            "base": 42,
        },
        environment=env,
    )
    assert result["copy"] == result["block"] == result["comment"] == 42
    assert result["literal"] == "{{ base }} {% invalid %} {# comment #}"
    with pytest.raises(CircularReferenceError):
        load_dict({"a": "[[ b ]]", "b": "[[ a ]]"}, environment=env)
    with pytest.raises(InvalidTemplateError):
        load_dict({"a": "[[ broken"}, environment=env)


def test_line_prefixes_are_detected() -> None:
    env = Environment(line_statement_prefix="%", line_comment_prefix="##")
    result = load_dict(
        {"block": "% if base\n42\n% endif", "comment": "42 ## ignored", "base": True},
        environment=env,
    )
    assert result["block"] == result["comment"] == 42
    with pytest.raises(CircularReferenceError):
        load_dict({"a": "% if a\n42\n% endif"}, environment=env)


@pytest.mark.parametrize("value", ["'%'", "  '%'", "first\n'%'", "'%.*'"])
def test_midline_statement_prefix_preserves_literal_strings(value: str) -> None:
    env = Environment(line_statement_prefix="%")
    assert not env.is_template(value)
    assert load_dict({"value": value}, environment=env)["value"] == value


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_indented_line_statement_prefix(newline: str) -> None:
    env = Environment(line_statement_prefix="%.*")
    value = newline.join([" \t%.* if base", "42", " \t%.* endif"])
    assert env.is_template(value)
    assert load_dict({"value": value, "base": True}, environment=env)["value"] == 42
