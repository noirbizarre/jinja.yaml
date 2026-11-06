"""Source attribution across the internal pipeline and public diagnostics."""

from __future__ import annotations

import sys

from collections import UserDict
from collections.abc import Callable
from pathlib import Path

import pytest

from jinja2 import DictLoader, TemplateSyntaxError

from jinja_yaml import (
    CircularReferenceError,
    DuplicateKeyError,
    Environment,
    InvalidTemplateError,
    MissingReferenceError,
    ResolutionError,
    SourceLocation,
    TemplateEvaluationError,
    load,
    load_dict,
    load_file,
    load_files,
)
from jinja_yaml.loader import _load_path
from jinja_yaml.merger import _merge, merge
from jinja_yaml.provenance import _SourceDocument
from jinja_yaml.resolver import _resolve, resolve
from jinja_yaml.types import Document, Node


def test_loaded_marks_include_containers_and_unambiguous_paths(
    write_yaml: Callable[[str, str], Path],
) -> None:
    path = write_yaml("marks.yaml", 'data:\n  - {"a.b[0]": null}\nempty: {}\nlist: []\n')
    document = _load_path(path)
    assert document.origins == {
        (): (SourceLocation(str(path), 1, 1),),
        ("data",): (SourceLocation(str(path), 2, 3),),
        ("data", 0): (SourceLocation(str(path), 2, 5),),
        ("data", 0, "a.b[0]"): (SourceLocation(str(path), 2, 16),),
        ("empty",): (SourceLocation(str(path), 3, 8),),
        ("list",): (SourceLocation(str(path), 4, 7),),
    }


@pytest.mark.parametrize("text", ["", "# comment\n", "null\n", "~\n"])
def test_empty_documents_have_only_available_marks(
    write_yaml: Callable[[str, str], Path], text: str
) -> None:
    path = write_yaml("empty.yaml", text)
    document = _resolve(_load_path(path))
    assert document.data == {}
    expected = {(): (SourceLocation(str(path), 1, 1),)} if text in {"null\n", "~\n"} else {}
    assert document.origins == expected


def test_identical_definitions_and_merged_containers_keep_all_origins(
    write_yaml: Callable[[str, str], Path],
) -> None:
    first = _load_path(write_yaml("a.yaml", "net:\n  port: 80\nitems: [{value: 1}]\n"))
    second = _load_path(write_yaml("b.yaml", "net:\n  host: localhost\nitems: [{value: 1}]\n"))
    third = _load_path(write_yaml("c.yaml", "net:\n  port: 80\n"))
    result = _merge(iter([first, second, third]))
    assert result.data == {"net": {"port": 80, "host": "localhost"}, "items": [{"value": 1}]}
    assert result.origins[()] == (*first.origins[()], *second.origins[()], *third.origins[()])
    assert result.origins[("net",)] == (
        *first.origins[("net",)],
        *second.origins[("net",)],
        *third.origins[("net",)],
    )
    assert result.origins[("net", "port")] == (
        *first.origins[("net", "port")],
        *third.origins[("net", "port")],
    )
    assert result.origins[("net", "host")] == second.origins[("net", "host")]
    for key in [("items",), ("items", 0), ("items", 0, "value")]:
        assert result.origins[key] == (*first.origins[key], *second.origins[key])


def test_conflict_reports_all_existing_contributors_and_incoming_source(
    write_yaml: Callable[[str, str], Path],
) -> None:
    paths = [
        write_yaml(f"{name}.yaml", f"port: {value}\n")
        for name, value in [("a", 80), ("b", 80), ("c", 81)]
    ]
    with pytest.raises(DuplicateKeyError) as excinfo:
        load_files(iter(paths))
    error = excinfo.value
    assert error.path == ("port",)
    assert error.existing_locations == tuple(SourceLocation(str(path), 1, 7) for path in paths[:2])
    assert error.incoming_locations == (SourceLocation(str(paths[2]), 1, 7),)
    assert all(str(path) in str(error) for path in paths)


def test_cross_file_resolution_preserves_declaration_origins_and_merge_order_independence(
    write_yaml: Callable[[str, str], Path],
) -> None:
    first = _load_path(write_yaml("base.yaml", "host: localhost\nport: 80\n"))
    second = _load_path(
        write_yaml("service.yaml", "url: 'http://{{ host }}:{{ port }}'\nport: 80\n")
    )
    forward = _resolve(_merge([first, second]))
    backward = _resolve(_merge([second, first]))
    assert (
        forward.data
        == backward.data
        == {"host": "localhost", "port": 80, "url": "http://localhost:80"}
    )
    assert forward.origins[("url",)] == second.origins[("url",)]
    assert forward.origins[("host",)] == first.origins[("host",)]
    assert forward.origins[("port",)] == (*first.origins[("port",)], *second.origins[("port",)])
    assert backward.origins[("port",)] == (*second.origins[("port",)], *first.origins[("port",)])


def test_identical_failing_templates_expose_every_declaration(
    write_yaml: Callable[[str, str], Path],
) -> None:
    paths = [write_yaml(f"{name}.yaml", "value: '{{ missing }}'\n") for name in ["a", "b"]]
    with pytest.raises(MissingReferenceError) as excinfo:
        load_files(paths)
    assert excinfo.value.source_locations == tuple(
        SourceLocation(str(path), 1, 8) for path in paths
    )
    assert excinfo.value.location == excinfo.value.source_locations[0]


def test_within_document_duplicates_report_key_token_locations(
    write_yaml: Callable[[str, str], Path],
) -> None:
    path = write_yaml("duplicate.yaml", "nested:\n  key: one\n  key: two\n")
    with pytest.raises(DuplicateKeyError) as excinfo:
        load_file(path)
    assert excinfo.value.existing_locations == (SourceLocation(str(path), 2, 3),)
    assert excinfo.value.incoming_locations == (SourceLocation(str(path), 3, 3),)


def test_merge_copies_alias_occurrences_without_cross_branch_contamination(
    write_yaml: Callable[[str, str], Path],
) -> None:
    first = _load_path(write_yaml("anchor.yaml", "base: &shared\n  x: 1\ncopy: *shared\n"))
    second = _load_path(write_yaml("extension.yaml", "base:\n  y: 2\n"))
    result = _merge([first, second])
    assert result.data == {"base": {"x": 1, "y": 2}, "copy": {"x": 1}}
    assert first.data == {"base": {"x": 1}, "copy": {"x": 1}}
    assert result.origins[("copy", "x")] == first.origins[("base", "x")]
    assert ("copy", "y") not in result.origins
    assert result.data["base"] is not result.data["copy"]
    assert result.data["copy"] is not first.data["copy"]


def test_plain_merge_does_not_mutate_inputs_even_on_conflict() -> None:
    items: list[Node] = [{"value": 1}]
    nested: Document = {"items": items}
    first: Document = {"nested": nested}
    second: Document = {"nested": {"new": 2, "items": []}}
    with pytest.raises(DuplicateKeyError):
        merge([first, second])
    assert first == {"nested": {"items": [{"value": 1}]}}
    result = merge([first])
    copied = result["nested"]
    assert isinstance(copied, dict)
    assert copied is not nested
    copied_items = copied["items"]
    assert isinstance(copied_items, list)
    assert copied_items is not items
    assert copied_items[0] is not items[0]


def test_cross_file_failure_identifies_failing_definition(
    write_yaml: Callable[[str, str], Path],
) -> None:
    first = write_yaml("url.yaml", 'url: "{{ servers }}"\n')
    second = write_yaml("servers.yaml", 'servers:\n  - host: "{{ domain }}"\n')
    with pytest.raises(MissingReferenceError) as excinfo:
        load(path for path in [first, second])
    error = excinfo.value
    assert error.key_path == ("servers", 0, "host")
    assert error.location == SourceLocation(str(second), 2, 11)
    assert error.source_locations == (error.location,)
    assert str(second) in str(error)
    assert error.dependency_chain[0] == ("url",)


@pytest.mark.parametrize(
    ("source", "error_type"),
    [
        ("{{ missing }}", MissingReferenceError),
        ("{{ data.missing }}", MissingReferenceError),
        ("{{ 1 / 0 }}", TemplateEvaluationError),
        ("{{ value }}", CircularReferenceError),
    ],
)
def test_resolution_failures_get_origins_automatically(
    write_yaml: Callable[[str, str], Path], source: str, error_type: type[ResolutionError]
) -> None:
    path = write_yaml("failure.yaml", f'value: "{source}"\n')
    with pytest.raises(error_type) as excinfo:
        load_file(path, namespaces={"data": {}})
    error = excinfo.value
    assert error.location == SourceLocation(str(path), 1, 8)
    assert error.source_locations == (error.location,)
    assert "line 1, column 8" in str(error)


@pytest.mark.parametrize("style", ["|", ">"])
def test_block_syntax_keeps_template_coordinates_separate_from_yaml(
    write_yaml: Callable[[str, str], Path], style: str
) -> None:
    path = write_yaml("syntax.yaml", f"value: {style}\n  first line\n  {{{{ oops\n")
    with pytest.raises(InvalidTemplateError) as excinfo:
        load_file(path)
    error = excinfo.value
    assert isinstance(error.__cause__, TemplateSyntaxError)
    assert error.location == SourceLocation(line=2 if style == "|" else 1)
    assert error.source_locations == (SourceLocation(str(path), 1, 8),)


@pytest.mark.parametrize("dynamic", [False, True])
def test_external_syntax_keeps_external_and_configuration_sources(
    write_yaml: Callable[[str, str], Path], dynamic: bool
) -> None:
    source = "{% include name %}" if dynamic else '{% include "broken" %}'
    path = write_yaml("include.yaml", f"value: '{source}'\nname: broken\n")
    environment = Environment(loader=DictLoader({"broken": "first\n{{ oops"}))
    with pytest.raises(InvalidTemplateError) as excinfo:
        load_file(path, environment=environment)
    assert excinfo.value.location == SourceLocation("broken", 2)
    assert excinfo.value.source_locations == (SourceLocation(str(path), 1, 8),)


def test_resolved_containers_inherit_template_declaration_without_rerendering(
    write_yaml: Callable[[str, str], Path],
) -> None:
    path = write_yaml(
        "generated.yaml",
        "original:\n  value: 42\ncopy: '{{ original }}'\nexternal: '{{ make() }}'\n",
    )
    calls = []

    def make() -> UserDict[str, object]:
        calls.append(True)
        return UserDict({"items": [42]})

    raw = _load_path(path)
    result = _resolve(raw, environment=Environment(globals={"make": make}), mapping_cls=UserDict)
    assert isinstance(result.data, UserDict)
    assert calls == [True]
    assert result.origins[("original", "value")] == raw.origins[("original", "value")]
    assert result.origins[("copy", "value")] == raw.origins[("copy",)]
    for key in [("external",), ("external", "items"), ("external", "items", 0)]:
        assert result.origins[key] == raw.origins[("external",)]


def test_metadata_is_optional_and_isolated_between_operations(
    write_yaml: Callable[[str, str], Path],
) -> None:
    path = write_yaml("file.yaml", 'value: "{{ missing }}"\n')
    with pytest.raises(MissingReferenceError) as first:
        load_file(path)
    with pytest.raises(MissingReferenceError) as second:
        load_dict({"value": "{{ missing }}"})
    assert first.value.source_locations
    assert second.value.location is None
    assert second.value.source_locations == ()
    assert _resolve(_SourceDocument({"value": "{{ 42 }}"})).origins == {}
    assert type(resolve({"value": "{{ 42 }}"})) is dict


def test_provenance_does_not_reject_recursive_template_results(
    write_yaml: Callable[[str, str], Path],
) -> None:
    # Template-produced values, unlike document input, need not be trees.
    recursive: dict[str, object] = {}
    recursive["self"] = recursive
    path = write_yaml("recursive-result.yaml", "value: '{{ external }}'\n")
    result = _resolve(_load_path(path), namespaces={"external": recursive})
    assert result.data["value"] is recursive
    assert result.origins[("value", "self")] == result.origins[("value",)]


def test_provenance_does_not_reject_deep_template_results(
    write_yaml: Callable[[str, str], Path],
) -> None:
    external: Node = 42
    depth = sys.getrecursionlimit() + 10
    for _ in range(depth):
        external = [external]
    path = write_yaml("deep-result.yaml", "value: '{{ external }}'\n")
    result = _resolve(_load_path(path), namespaces={"external": external})
    assert result.data["value"] is external
    assert result.origins[("value",) + (0,) * depth] == result.origins[("value",)]


def test_extension_domain_error_is_preserved_with_file_metadata(
    write_yaml: Callable[[str, str], Path],
) -> None:
    original = MissingReferenceError(("extension",), "private")

    def fail() -> None:
        raise original

    path = write_yaml("extension.yaml", "value: '{{ fail() }}'\n")
    with pytest.raises(MissingReferenceError) as excinfo:
        load_file(path, environment=Environment(globals={"fail": fail}))
    assert excinfo.value is original
    assert original.source_locations == ()
    assert original.location is None


def test_override_replaces_origins_and_removes_obsolete_descendants(
    write_yaml: Callable[[str, str], Path],
) -> None:
    first = _load_path(
        write_yaml(
            "base.yaml",
            "net: {port: 80, host: localhost}\nitems: [{old: 1}, 2]\nequal: [{x: 1}]\n",
        )
    )
    second = _load_path(
        write_yaml("override.yaml", "net: {port: 443}\nitems: []\nequal: [{x: 1}]\n")
    )
    result = _merge([first, second], merge_strategy="override")
    assert result.data == {
        "net": {"port": 443, "host": "localhost"},
        "items": [],
        "equal": [{"x": 1}],
    }
    assert result.origins[()] == (*first.origins[()], *second.origins[()])
    assert result.origins[("net",)] == (*first.origins[("net",)], *second.origins[("net",)])
    assert result.origins[("net", "host")] == first.origins[("net", "host")]
    assert result.origins[("net", "port")] == second.origins[("net", "port")]
    assert result.origins[("items",)] == second.origins[("items",)]
    assert ("items", 0) not in result.origins
    assert ("items", 0, "old") not in result.origins
    assert ("items", 1) not in result.origins
    for path in [("equal",), ("equal", 0), ("equal", 0, "x")]:
        assert result.origins[path] == second.origins[path]


def test_override_category_changes_then_recursive_merge_keep_only_live_origins(
    write_yaml: Callable[[str, str], Path],
) -> None:
    first = _load_path(write_yaml("first.yaml", "value: {old: 1}\n"))
    second = _load_path(write_yaml("second.yaml", "value: null\n"))
    replaced = _merge([first, second], merge_strategy="override")
    assert replaced.data == {"value": None}
    assert ("value", "old") not in replaced.origins
    third = _load_path(write_yaml("third.yaml", "value: {new: 2}\n"))
    fourth = _load_path(write_yaml("fourth.yaml", "value: {more: 3}\n"))
    result = _merge([replaced, third, fourth], merge_strategy="override")
    assert result.data == {"value": {"new": 2, "more": 3}}
    assert result.origins[("value",)] == (*third.origins[("value",)], *fourth.origins[("value",)])
    assert result.origins[("value", "new")] == third.origins[("value", "new")]
    assert result.origins[("value", "more")] == fourth.origins[("value", "more")]
    assert ("value", "old") not in result.origins
    # A replacement without metadata must also remove the old attribution.
    unmarked = _merge([result, _SourceDocument({"value": []})], merge_strategy="override")
    assert not any(path and path[0] == "value" for path in unmarked.origins)


def test_override_equal_failing_templates_report_only_winning_source(
    write_yaml: Callable[[str, str], Path],
) -> None:
    paths = [write_yaml(f"{name}.yaml", "value: '{{ missing }}'\n") for name in ["a", "b"]]
    with pytest.raises(MissingReferenceError) as excinfo:
        load_files(paths, merge_strategy="override")
    assert excinfo.value.source_locations == (SourceLocation(str(paths[1]), 1, 8),)
    assert excinfo.value.location == excinfo.value.source_locations[0]


def test_override_alias_replacement_is_isolated(
    write_yaml: Callable[[str, str], Path],
) -> None:
    first = _load_path(write_yaml("first.yaml", "base: old\n"))
    second = _load_path(write_yaml("alias.yaml", "base: &shared\n  x: 1\ncopy: *shared\n"))
    third = _load_path(write_yaml("third.yaml", "base: {x: 2}\n"))
    result = _merge([first, second, third], merge_strategy="override")
    assert result.data == {"base": {"x": 2}, "copy": {"x": 1}}
    assert second.data == {"base": {"x": 1}, "copy": {"x": 1}}
    assert result.origins[("base", "x")] == third.origins[("base", "x")]
    assert result.origins[("copy", "x")] == second.origins[("base", "x")]
    assert result.data["base"] is not result.data["copy"]
