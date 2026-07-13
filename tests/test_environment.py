"""Tests for the configurable Jinja environment."""

from __future__ import annotations

import pytest

from jinja_yaml import load_dict
from jinja_yaml.environment import Environment
from jinja_yaml.exceptions import ResolutionError


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
