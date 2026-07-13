"""Tests for externally injected namespaces."""

from __future__ import annotations

import pytest

from jinja_yaml import load_dict
from jinja_yaml.exceptions import NamespaceCollisionError


def test_namespace_reference() -> None:
    result = load_dict(
        {"url": "https://{{ data.domain }}"},
        namespaces={"data": {"domain": "example.com"}},
    )
    assert result["url"] == "https://example.com"


def test_multiple_namespaces() -> None:
    result = load_dict(
        {"dsn": "{{ env.HOST }}:{{ secrets.token }}"},
        namespaces={"env": {"HOST": "db"}, "secrets": {"token": "s3cr3t"}},
    )
    assert result["dsn"] == "db:s3cr3t"


def test_namespace_and_document_reference_combined() -> None:
    result = load_dict(
        {"fqdn": "{{ host }}.{{ data.domain }}", "host": "nas"},
        namespaces={"data": {"domain": "home.arpa"}},
    )
    assert result["fqdn"] == "nas.home.arpa"


def test_namespace_collision_raises() -> None:
    with pytest.raises(NamespaceCollisionError) as excinfo:
        load_dict({"data": "value"}, namespaces={"data": {}})
    assert excinfo.value.name == "data"


def test_namespace_native_value_is_preserved() -> None:
    result = load_dict({"cfg": "{{ data }}"}, namespaces={"data": {"a": 1}})
    assert result["cfg"] == {"a": 1}
