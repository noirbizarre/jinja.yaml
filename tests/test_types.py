"""Tests for the shared type helpers."""

from __future__ import annotations

from collections import UserDict
from pathlib import Path
from typing import Any, assert_type

import pytest

from jinja_yaml import Environment, load, load_dict, load_file, load_files
from jinja_yaml.loader import load_mapping
from jinja_yaml.resolver import resolve
from jinja_yaml.types import format_key_path


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ((), "<root>"),
        (("domain",), "domain"),
        (("net", "domain"), "net.domain"),
        (("hosts", 0), "hosts[0]"),
        (("net", "hosts", 1, "name"), "net.hosts[1].name"),
    ],
)
def test_format_key_path(path: tuple[str | int, ...], expected: str) -> None:
    assert format_key_path(path) == expected


def test_resolved_api_types_and_native_objects(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("result: '{{ make() }}'\n")
    value = object()
    env = Environment(globals={"make": lambda: value})
    raw = load_mapping({"result": "{{ make() }}"})

    default_results = [
        assert_type(load_dict(raw, environment=env), dict[str, Any]),
        assert_type(load_file(path, environment=env), dict[str, Any]),
        assert_type(load_files([path], environment=env), dict[str, Any]),
        assert_type(load(raw, environment=env), dict[str, Any]),
        assert_type(resolve(raw, environment=env), dict[str, Any]),
    ]
    custom_results = [
        assert_type(
            load_dict(raw, environment=env, mapping_cls=UserDict[str, Any]), UserDict[str, Any]
        ),
        assert_type(
            load_file(path, environment=env, mapping_cls=UserDict[str, Any]), UserDict[str, Any]
        ),
        assert_type(
            load_files([path], environment=env, mapping_cls=UserDict[str, Any]), UserDict[str, Any]
        ),
        assert_type(load(raw, environment=env, mapping_cls=UserDict[str, Any]), UserDict[str, Any]),
        assert_type(
            resolve(raw, environment=env, mapping_cls=UserDict[str, Any]), UserDict[str, Any]
        ),
    ]
    for result in default_results:
        assert isinstance(result, dict)
        assert result["result"] is value
    for result in custom_results:
        assert isinstance(result, UserDict)
        assert result["result"] is value
