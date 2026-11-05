"""Tests for the loading phase."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

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


@pytest.mark.parametrize("text", ["", "# comment\n", "null\n", "~\n", "---\n"])
def test_empty_and_null_documents(write_yaml: Callable[[str, str], Path], text: str) -> None:
    assert loader.load_path(write_yaml("empty.yaml", text)) == {}


def test_valid_nested_yaml_and_aliases(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml(
        "valid.yaml",
        'data: &data {values: [text, 1, 1.5, true, null], date: "2026-01-01"}\ncopy: *data\n',
    )
    expected = {"values": ["text", 1, 1.5, True, None], "date": "2026-01-01"}
    assert loader.load_path(path) == {"data": expected, "copy": expected}


@pytest.mark.parametrize(
    ("text", "message", "position", "key_path"),
    [
        ("[1, 2]\n", "Expected a mapping", "line 1, column 1", "<root>"),
        ("hello\n", "Expected a mapping", "line 1, column 1", "<root>"),
        ("outer:\n  1: bad\n", "keys must be strings", "line 2, column 3", "outer"),
        ("items:\n  - {true: bad}\n", "keys must be strings", "line 2, column 6", "items[0]"),
        ("? [a, b]\n: bad\n", "keys must be strings", "line 1, column 3", "<root>"),
        ("? {a: b}\n: bad\n", "keys must be strings", "line 1, column 3", "<root>"),
        ("outer:\n  date: 2026-01-01\n", "Unsupported YAML type", "line 2, column 9", "outer.date"),
        ("data: !!binary YQ==\n", "Unsupported YAML type", "line 1, column 7", "data"),
        ("data: !!set {a: null}\n", "Unsupported YAML type", "line 1, column 7", "data"),
        ("data: !custom abc\n", "Unsupported YAML type", "line 1, column 7", "data"),
        ("data: !!int abc\n", "Invalid scalar", "line 1, column 7", "data"),
        ("data: !!int ''\n", "Invalid scalar", "line 1, column 7", "data"),
        ("data: !!bool abc\n", "Invalid scalar", "line 1, column 7", "data"),
        ("data: !!float abc\n", "Invalid scalar", "line 1, column 7", "data"),
        ("data: {<<: {a: 1}}\n", "merge keys (<<) are unsupported", "line 1, column 8", "data"),
        ("data: &a [*a]\n", "Recursive YAML structure", "line 1, column 7", "data[0]"),
        ("data: &a {child: *a}\n", "Recursive YAML structure", "line 1, column 7", "data.child"),
    ],
)
def test_yaml_validation_diagnostics(
    write_yaml: Callable[[str, str], Path],
    text: str,
    message: str,
    position: str,
    key_path: str,
) -> None:
    path = write_yaml("invalid.yaml", text)
    with pytest.raises(LoadError) as excinfo:
        loader.load_path(path)
    error = str(excinfo.value)
    assert message in error
    assert str(path) in error
    assert position in error
    assert repr(key_path) in error
    if message in {"Unsupported YAML type", "Invalid scalar"}:
        assert isinstance(excinfo.value.__cause__, yaml.YAMLError)


@pytest.mark.parametrize("second", ["first", "different"])
def test_nested_duplicate_reports_both_locations(
    write_yaml: Callable[[str, str], Path], second: str
) -> None:
    path = write_yaml("duplicate.yaml", f"items:\n  - key: first\n    key: {second}\n")
    with pytest.raises(DuplicateKeyError) as excinfo:
        loader.load_path(path)
    assert excinfo.value.path == ("items", 0, "key")
    message = str(excinfo.value)
    assert str(path) in message
    assert "'items[0].key'" in message
    assert "line 3, column 5" in message
    assert "first defined at line 2, column 5" in message


def test_direct_strict_loader_rejects_duplicates() -> None:
    with pytest.raises(DuplicateKeyError) as excinfo:
        yaml.load("outer: {key: 1, key: 1}", Loader=loader.StrictSafeLoader)
    assert excinfo.value.path == ("outer", "key")


def test_quoted_merge_key_is_a_string(write_yaml: Callable[[str, str], Path]) -> None:
    assert loader.load_path(write_yaml("literal.yaml", '"<<": value\n')) == {"<<": "value"}


@pytest.mark.parametrize("text", ["key: : :\n", "a: 1\n---\nb: 2\n", "key: \0\n"])
def test_parser_error_preserves_cause(write_yaml: Callable[[str, str], Path], text: str) -> None:
    path = write_yaml("syntax.yaml", text)
    with pytest.raises(LoadError) as excinfo:
        loader.load_path(path)
    assert str(path) in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, yaml.YAMLError)
    if isinstance(excinfo.value.__cause__, yaml.MarkedYAMLError):
        assert "line" in str(excinfo.value)
        assert "column" in str(excinfo.value)


def test_read_error_preserves_cause(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"
    with pytest.raises(LoadError) as excinfo:
        loader.load_path(path)
    assert str(path) in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, OSError)


def test_invalid_utf8_preserves_cause(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_bytes(b"key: \xff\n")
    with pytest.raises(LoadError) as excinfo:
        loader.load_path(path)
    assert str(path) in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, UnicodeDecodeError)


@pytest.mark.parametrize("value", [date(2026, 1, 1), b"a", {1}, (1,), object()])
def test_mapping_rejects_unsupported_leaves(value: object) -> None:
    with pytest.raises(LoadError) as excinfo:
        loader.load_mapping({"items": [{"value": value}]})
    assert type(value).__name__ in str(excinfo.value)
    assert "'items[0].value'" in str(excinfo.value)
    assert "in-memory mapping" in str(excinfo.value)


def test_mapping_nested_invalid_key() -> None:
    with pytest.raises(LoadError, match=r"items\[0\]"):
        loader.load_mapping({"items": [{1: "value"}]})


@pytest.mark.parametrize("kind", ["dict", "list"])
def test_mapping_rejects_cycles(kind: str) -> None:
    container: Any = {} if kind == "dict" else []
    if kind == "dict":
        container["child"] = container
    else:
        container.append(container)
    with pytest.raises(LoadError, match="Recursive in-memory"):
        loader.load_mapping({"data": container})


def test_mapping_copies_shared_acyclic_containers() -> None:
    shared = {"values": ["text", 1, 1.5, True, None]}
    source = {"a": shared, "b": shared}
    result = loader.load_mapping(source)
    assert result == source
    assert result["a"] is not shared
    assert result["b"] is not shared
    assert isinstance(result["a"], dict)
    assert result["a"]["values"] is not shared["values"]
