"""Shared fixtures for the test suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def write_yaml(tmp_path: Path) -> Callable[[str, str], Path]:
    """Return a helper that writes YAML content to a temp file and returns it."""

    def _write(name: str, content: str) -> Path:
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    return _write
