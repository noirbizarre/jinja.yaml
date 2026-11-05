"""Tests for the public API surface."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from jinja_yaml import load, load_dict, load_file, load_files
from jinja_yaml.exceptions import DuplicateKeyError, LoadError


def test_load_dict_returns_plain_dict() -> None:
    result = load_dict({"a": 1})
    assert isinstance(result, dict)
    assert result == {"a": 1}


def test_load_dict_does_not_mutate_input() -> None:
    source = {"fqdn": "nas.{{ domain }}", "domain": "home.arpa"}
    snapshot = {"fqdn": "nas.{{ domain }}", "domain": "home.arpa"}
    load_dict(source)
    assert source == snapshot


def test_load_file(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("config.jinja.yaml", "fqdn: nas.{{ domain }}\ndomain: home.arpa\n")
    assert load_file(path)["fqdn"] == "nas.home.arpa"


def test_load_files_merges_across_documents(write_yaml: Callable[[str, str], Path]) -> None:
    first = write_yaml("a.jinja.yaml", "domain: home.arpa\n")
    second = write_yaml("b.jinja.yaml", "fqdn: nas.{{ domain }}\n")
    assert load_files([first, second])["fqdn"] == "nas.home.arpa"


def test_load_files_reports_cross_document_duplicates(
    write_yaml: Callable[[str, str], Path],
) -> None:
    first = write_yaml("a.jinja.yaml", "domain: a\n")
    second = write_yaml("b.jinja.yaml", "domain: b\n")
    with pytest.raises(DuplicateKeyError):
        load_files([first, second])


def test_load_file_reports_validation_error(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("invalid.yaml", "data: 2026-01-01\n")
    with pytest.raises(LoadError) as excinfo:
        load_file(path)
    assert str(path) in str(excinfo.value)
    assert "line 1, column 7" in str(excinfo.value)
    assert excinfo.value.__cause__ is not None


def test_load_files_identifies_invalid_file(write_yaml: Callable[[str, str], Path]) -> None:
    first = write_yaml("valid.yaml", "data: 1\n")
    second = write_yaml("invalid.yaml", "items: {key: 1, key: 1}\n")
    with pytest.raises(DuplicateKeyError) as excinfo:
        load_files([first, second])
    assert str(second) in str(excinfo.value)
    assert excinfo.value.path == ("items", "key")


def test_load_dict_validates_before_resolution() -> None:
    with pytest.raises(LoadError, match="Unsupported value type bytes"):
        load_dict({"data": b"value"})


def test_load_dispatches_on_dict() -> None:
    assert load({"a": 1}) == {"a": 1}


def test_load_dispatches_on_path(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("config.jinja.yaml", "a: 1\n")
    assert load(path) == {"a": 1}
    assert load(str(path)) == {"a": 1}


def test_load_dispatches_on_iterable_of_paths(write_yaml: Callable[[str, str], Path]) -> None:
    first = write_yaml("a.jinja.yaml", "a: 1\n")
    second = write_yaml("b.jinja.yaml", "b: 2\n")
    assert load([first, second]) == {"a": 1, "b": 2}


def test_load_rejects_unsupported_source() -> None:
    with pytest.raises(LoadError):
        load(42)  # ty: ignore[invalid-argument-type]


class MyDict(dict[str, object]):
    """A trivial ``dict`` subclass used to check ``mapping_cls`` threading."""


def test_mapping_cls_defaults_to_dict() -> None:
    result = load_dict({"a": "{{ b }}", "b": 1})
    assert type(result) is dict


def test_mapping_cls_applied_to_output() -> None:
    result = load_dict({"a": "{{ b }}", "b": 1}, mapping_cls=MyDict)
    assert type(result) is MyDict
    assert result == {"a": 1, "b": 1}


def test_mapping_cls_applied_to_nested() -> None:
    result = load_dict({"net": {"domain": "home.arpa"}}, mapping_cls=MyDict)
    assert isinstance(result["net"], MyDict)


def test_mapping_cls_via_load_file(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("config.jinja.yaml", "fqdn: nas.{{ domain }}\ndomain: home.arpa\n")
    result = load_file(path, mapping_cls=MyDict)
    assert type(result) is MyDict
    assert result["fqdn"] == "nas.home.arpa"


def test_mapping_cls_via_load(write_yaml: Callable[[str, str], Path]) -> None:
    path = write_yaml("config.jinja.yaml", "a: 1\n")
    assert type(load(path, mapping_cls=MyDict)) is MyDict
    assert type(load({"a": 1}, mapping_cls=MyDict)) is MyDict
