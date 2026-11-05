"""Public resolution diagnostics and the failures they describe."""

from __future__ import annotations

import pytest

from jinja2 import DictLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError

from jinja_yaml import (
    CircularReferenceError,
    Environment,
    InvalidTemplateError,
    MissingReferenceError,
    ResolutionError,
    SourceLocation,
    TemplateEvaluationError,
    load_dict,
)


def test_missing_root_reports_dependency_chain_and_nested_key() -> None:
    with pytest.raises(MissingReferenceError) as excinfo:
        load_dict({"url": "{{ servers }}", "servers": [{"host": "{{ domain }}"}]})
    error = excinfo.value
    assert error.key_path == ("servers", 0, "host")
    assert error.reference == "domain"
    assert error.dependency_chain == (
        ("url",),
        ("servers",),
        ("servers", 0),
        ("servers", 0, "host"),
    )
    assert "servers[0].host" in str(error)
    assert "domain" in str(error)
    assert error.__cause__ is None
    assert error.location is None


@pytest.mark.parametrize(
    "source", ["{{ data.missing }}", "prefix-{{ data.missing }}", "{{ data[3] }}"]
)
def test_missing_nested_lookup_preserves_jinja_cause(source: str) -> None:
    with pytest.raises(MissingReferenceError) as excinfo:
        load_dict({"result": source}, namespaces={"data": {"present": 1}})
    error = excinfo.value
    assert error.key_path == ("result",)
    assert error.dependency_chain == (("result",),)
    assert error.reference is None
    assert isinstance(error.__cause__, UndefinedError)
    assert str(error.__cause__) in str(error)


def test_default_filter_handles_missing_nested_lookup() -> None:
    assert load_dict(
        {"result": "{{ data.missing | default('fallback') }}"}, namespaces={"data": {}}
    ) == {"result": "fallback"}


def test_syntax_error_retains_template_line() -> None:
    with pytest.raises(InvalidTemplateError) as excinfo:
        load_dict({"nested": [{"value": "first line\n{{ oops"}]})
    error = excinfo.value
    assert error.key_path == ("nested", 0, "value")
    assert isinstance(error.__cause__, TemplateSyntaxError)
    assert error.location == SourceLocation(line=2)
    assert error.dependency_chain == ()


@pytest.mark.parametrize("dynamic", [False, True])
def test_loaded_syntax_error_retains_source_name(dynamic: bool) -> None:
    env = Environment(loader=DictLoader({"broken": "first line\n{{ oops"}))
    source = "{% include name %}" if dynamic else '{% include "broken" %}'
    with pytest.raises(InvalidTemplateError) as excinfo:
        load_dict({"result": source, "name": "broken"}, environment=env)
    error = excinfo.value
    assert error.key_path == ("result",)
    assert error.location == SourceLocation("broken", 2)
    assert isinstance(error.__cause__, TemplateSyntaxError)


def test_missing_loader_template_is_a_template_failure() -> None:
    with pytest.raises(InvalidTemplateError) as excinfo:
        load_dict(
            {"result": '{% include "absent" %}'}, environment=Environment(loader=DictLoader({}))
        )
    assert excinfo.value.key_path == ("result",)
    assert isinstance(excinfo.value.__cause__, TemplateNotFound)


@pytest.mark.parametrize(
    ("expression", "cause"),
    [("1 / 0", ZeroDivisionError), ("1 + 'text'", TypeError)],
)
def test_python_evaluation_errors_are_wrapped(expression: str, cause: type[Exception]) -> None:
    with pytest.raises(TemplateEvaluationError) as excinfo:
        load_dict({"outer": "{{ value }}", "value": "{{ " + expression + " }}"})
    error = excinfo.value
    assert error.key_path == ("value",)
    assert error.dependency_chain == (("outer",), ("value",))
    assert isinstance(error.__cause__, cause)
    assert cause.__name__ in str(error)
    assert "value" in str(error)


@pytest.mark.parametrize("extension", ["filter", "global"])
def test_custom_extension_error_preserves_original_exception(extension: str) -> None:
    original = ValueError("invalid port")

    def fail(value: object = None) -> None:
        raise original

    env = Environment(filters={"fail": fail}, globals={"fail": fail})
    source = "{{ port | fail }}" if extension == "filter" else "{{ fail(port) }}"
    with pytest.raises(TemplateEvaluationError) as excinfo:
        load_dict({"result": source, "port": 80}, environment=env)
    assert excinfo.value.__cause__ is original
    assert "invalid port" in str(excinfo.value)
    assert excinfo.value.key_path == ("result",)


def test_extension_domain_error_is_not_rewrapped() -> None:
    original = ResolutionError("extension resolution failure")

    def fail() -> None:
        raise original

    with pytest.raises(ResolutionError) as excinfo:
        load_dict({"result": "{{ fail() }}"}, environment=Environment(globals={"fail": fail}))
    assert excinfo.value is original


def test_cycle_has_common_diagnostic_context_and_closed_path() -> None:
    with pytest.raises(CircularReferenceError) as excinfo:
        load_dict({"a": [{"ref": "{{ b }}"}], "b": "{{ a }}"})
    error = excinfo.value
    assert error.key_path == ("a",)
    assert error.dependency_chain == tuple(error.path)
    assert error.path == [("a",), ("a", 0), ("a", 0, "ref"), ("b",), ("a",)]
    assert "a[0].ref" in str(error)
    assert error.__cause__ is None


def test_diagnostic_can_carry_future_yaml_source_metadata() -> None:
    location = SourceLocation("config.jinja.yaml", 4, 7)
    error = MissingReferenceError(("host",), "domain", location=location)
    assert error.location == location
    assert error.location.source == "config.jinja.yaml"
    assert error.location.line == 4
    assert error.location.column == 7
