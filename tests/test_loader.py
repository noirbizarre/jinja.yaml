"""Tests for the loading phase."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from jinja_yaml import loader
from jinja_yaml.exceptions import DuplicateKeyError, LoadError


def test_load_single_file(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("config.jinja.yaml", "domain: home.arpa\nport: 8080\n")
    assert loader.load_path(path) == {"domain": "home.arpa", "port": 8080}


def test_load_file_accepts_string_path(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("config.jinja.yaml", "domain: home.arpa\n")
    assert loader.load_path(str(path)) == {"domain": "home.arpa"}


def test_load_empty_file_yields_empty_document(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("empty.jinja.yaml", "")
    assert loader.load_path(path) == {}


def test_load_multiple_files(write_yaml: Callable[[str, str], Path]) -> None:
    first = write_yaml("a.jinja.yaml", "a: 1\n")
    second = write_yaml("b.jinja.yaml", "b: 2\n")
    assert loader.load_paths([first, second]) == [{"a": 1}, {"b": 2}]


def test_load_mapping_deep_copies_input() -> None:
    source: dict[str, object] = {"nested": {"value": 1}, "items": [1, 2]}
    loaded = loader.load_mapping(source)
    assert loaded == source
    assert loaded["nested"] is not source["nested"]
    assert loaded["items"] is not source["items"]


def test_duplicate_key_within_document(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("dup.jinja.yaml", "domain: a\ndomain: b\n")
    with pytest.raises(DuplicateKeyError) as excinfo:
        loader.load_path(path)
    assert excinfo.value.path == ("domain",)


def test_invalid_yaml_raises_load_error(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("bad.jinja.yaml", "key: : :\n")
    with pytest.raises(LoadError):
        loader.load_path(path)


def test_non_mapping_top_level_raises(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("list.jinja.yaml", "- 1\n- 2\n")
    with pytest.raises(LoadError):
        loader.load_path(path)


def test_missing_file_raises_load_error(tmp_path: Path) -> None:
    with pytest.raises(LoadError):
        loader.load_path(tmp_path / "does-not-exist.jinja.yaml")


def test_load_mapping_rejects_non_mapping() -> None:
    with pytest.raises(LoadError):
        loader.load_mapping([1, 2])  # ty: ignore[invalid-argument-type]


def test_load_mapping_rejects_non_string_keys() -> None:
    with pytest.raises(LoadError):
        loader.load_mapping({1: "value"})  # ty: ignore[invalid-argument-type]
