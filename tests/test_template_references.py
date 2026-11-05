"""Loader-backed references use Jinja's context and scoping rules."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from jinja2 import DictLoader
from jinja2 import Environment as JinjaEnvironment

from jinja_yaml import load_dict
from jinja_yaml.environment import Environment
from jinja_yaml.exceptions import CircularReferenceError, InvalidTemplateError, ResolutionError


def environment(templates: dict[str, str]) -> Environment:
    return Environment(loader=DictLoader(templates))


def test_transitive_include_dependencies() -> None:
    env = environment({"outer": '{% include "inner" %}', "inner": "{{ value }}"})
    result = load_dict(
        {"result": '{% include "outer" %}', "value": "{{ base }}", "base": 42},
        environment=env,
    )
    assert result["result"] == 42


@pytest.mark.parametrize(
    "source",
    [
        '{% set item = value %}{% include "part" %}',
        '{% for item in [value] %}{% include "part" %}{% endfor %}',
        '{% with item = value %}{% include "part" %}{% endwith %}',
        '{% macro render(item) %}{% include "part" %}{% endmacro %}{{ render(value) }}',
    ],
)
def test_include_receives_locals_without_false_document_cycle(source: str) -> None:
    env = environment({"part": "{{ item }}"})
    assert env.referenced_variables(source) == {"value"}
    result = load_dict({"item": source, "value": 42}, environment=env)
    assert result["item"] == 42


def test_assignment_order_and_scope_exit() -> None:
    env = environment({"part": "{{ item }}"})
    assert env.referenced_variables('{% include "part" %}{% set item = 1 %}') == {"item"}
    assert env.referenced_variables('{% with item = 1 %}{% endwith %}{% include "part" %}') == {
        "item"
    }


@pytest.mark.parametrize("tag", ['import "macros" as m', 'from "macros" import show'])
def test_import_context_boundary(tag: str) -> None:
    env = environment({"macros": "{% macro show() %}value={{ value }}{% endmacro %}"})
    call = "m.show()" if tag.startswith("import") else "show()"
    source = "{% " + tag + " %}{{ " + call + " }}"
    assert env.referenced_variables(source) == set()
    with pytest.raises(ResolutionError, match="value"):
        load_dict({"result": source, "value": 42}, environment=env)
    source = "{% " + tag + " with context %}{{ " + call + " }}"
    assert load_dict({"result": source, "value": 42}, environment=env)["result"] == "value=42"


def test_no_context_include_uses_only_globals() -> None:
    env = Environment(loader=DictLoader({"part": "{{ value }}"}), globals={"value": 7})
    result = load_dict(
        {"result": '{% include "part" without context %}', "value": "{{ result }}"},
        environment=env,
    )
    assert result == {"result": 7, "value": 7}


def test_inheritance_observes_child_assignments_after_extends() -> None:
    env = environment({"parent": "{{ item }}{% block body %}{{ value }}{% endblock %}"})
    source = '{% extends "parent" %}{% set item = prefix %}'
    result = load_dict({"result": source, "prefix": "hello-", "value": "world"}, environment=env)
    assert result["result"] == "hello-world"


def test_inherited_blocks_and_super() -> None:
    env = environment({"parent": "{% block body %}{{ value }}{% endblock %}"})
    source = '{% extends "parent" %}{% block body %}{{ super() }}!{% endblock %}'
    assert load_dict({"result": source, "value": "yes"}, environment=env)["result"] == "yes!"


def test_include_fallback_selects_only_first_available() -> None:
    env = environment({"selected": "{{ value }}", "unused": "{{ missing }}"})
    source = '{% include ["absent", "selected", "unused"] %}'
    assert env.referenced_variables(source) == {"value"}
    assert load_dict({"result": source, "value": 42}, environment=env)["result"] == 42


def test_ignored_missing_include() -> None:
    assert load_dict(
        {"result": '{% include "absent" ignore missing %}'}, environment=environment({})
    ) == {"result": None}


def test_required_missing_template_has_configuration_context() -> None:
    with pytest.raises(ResolutionError, match=r"result.*absent") as excinfo:
        load_dict({"result": '{% include "absent" %}'}, environment=environment({}))
    assert excinfo.value.__cause__ is not None


def test_invalid_preferred_template_does_not_fall_back() -> None:
    env = environment({"broken": "{{", "fallback": "fine"})
    with pytest.raises(InvalidTemplateError, match="result") as excinfo:
        load_dict({"result": '{% include ["broken", "fallback"] %}'}, environment=env)
    assert "broken" in str(excinfo.value)


def test_recursive_static_template_chain_has_context() -> None:
    env = environment({"one": '{% include "two" %}', "two": '{% include "one" %}'})
    with pytest.raises(ResolutionError, match=r"result.*one -> two -> one"):
        load_dict({"result": '{% include "one" %}'}, environment=env)


def test_dynamic_template_name_retains_runtime_behavior() -> None:
    env = environment({"part": "{{ supplied }}"})
    source = "{% set supplied = value %}{% include name %}"
    assert env.referenced_variables(source) == {"value", "name"}
    assert (
        load_dict({"result": source, "name": "part", "value": 42}, environment=env)["result"] == 42
    )


def test_loaded_template_can_close_a_configuration_cycle() -> None:
    env = environment({"part": "{{ other }}"})
    with pytest.raises(CircularReferenceError) as excinfo:
        load_dict({"result": '{% include "part" %}', "other": "{{ result }}"}, environment=env)
    assert excinfo.value.path == [("result",), ("other",), ("result",)]


def test_dynamic_target_dependencies_are_not_guessed() -> None:
    env = environment({"part": "value={{ hidden }}"})
    with pytest.raises(ResolutionError, match=r"result.*hidden"):
        load_dict({"result": "{% include name %}", "name": "part", "hidden": 42}, environment=env)


def test_overridden_parent_blocks_are_analyzed_conservatively() -> None:
    env = environment({"parent": "{% block body %}{{ unused }}{% endblock %}"})
    source = '{% extends "parent" %}{% block body %}replacement{% endblock %}'
    assert env.referenced_variables(source) == {"unused"}


def test_relative_loader_names_follow_environment_join_path() -> None:
    class RelativeEnvironment(Environment):
        def join_path(self, template: str, parent: str) -> str:
            return parent.rsplit("/", 1)[0] + "/" + template

    env = RelativeEnvironment(
        loader=DictLoader({"dir/outer": '{% include "inner" %}', "dir/inner": "{{ value }}"})
    )
    assert (
        load_dict({"result": '{% include "dir/outer" %}', "value": 42}, environment=env)["result"]
        == 42
    )


def test_analysis_is_reused_when_building_render_context() -> None:
    class CountingEnvironment(Environment):
        calls = 0

        def referenced_variables(self, source: str) -> set[str]:
            self.calls += 1
            return super().referenced_variables(source)

    env = CountingEnvironment(loader=DictLoader({"part": "{{ value }}"}))
    assert (
        load_dict({"result": '{% include "part" %}', "value": 42}, environment=env)["result"] == 42
    )
    assert env.calls == 1


def test_static_reference_without_loader_has_context() -> None:
    with pytest.raises(ResolutionError, match=r"result.*part.*no loader"):
        load_dict({"result": '{% include "part" %}'})


def test_dynamic_missing_template_has_context() -> None:
    with pytest.raises(ResolutionError, match=r"result.*absent"):
        load_dict({"result": "{% include name %}", "name": "absent"}, environment=environment({}))


def test_diamond_references_reuse_loaded_source() -> None:
    class CountingLoader(DictLoader):
        calls = 0

        def get_source(
            self, environment: JinjaEnvironment, template: str
        ) -> tuple[str, None, Callable[[], bool]]:
            self.calls += 1
            return super().get_source(environment, template)

    loader = CountingLoader(
        {
            "left": '{% include "shared" %}',
            "right": '{% include "shared" %}',
            "shared": "{{ value }}",
        }
    )
    env = Environment(loader=loader)
    assert env.referenced_variables('{% include "left" %}{% include "right" %}') == {"value"}
    assert loader.calls == 3
