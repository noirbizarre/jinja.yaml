"""Tests for the shared type helpers."""

from __future__ import annotations

import pytest

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
