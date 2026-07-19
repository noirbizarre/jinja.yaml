"""jinja.yaml — YAML configuration with dependency-aware Jinja templating."""

from __future__ import annotations

from .api import load, load_dict, load_file, load_files
from .environment import Environment
from .exceptions import (
    CircularReferenceError,
    DuplicateKeyError,
    InvalidTemplateError,
    JinjaYamlError,
    LoadError,
    MergeError,
    NamespaceCollisionError,
    ResolutionError,
)


def _resolve_version() -> str:
    """Return the package version.

    The version is written into ``VERSION`` at build time by pdm-backend from
    the Git tags. When running from a source checkout (no build artifact), fall
    back to the installed distribution metadata, then to a dev placeholder.
    """
    from pathlib import Path

    version_file = Path(__file__).parent / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()

    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("jinja.yaml")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _resolve_version()

__all__ = [
    "__version__",
    "load",
    "load_dict",
    "load_file",
    "load_files",
    "Environment",
    "JinjaYamlError",
    "LoadError",
    "MergeError",
    "DuplicateKeyError",
    "NamespaceCollisionError",
    "ResolutionError",
    "InvalidTemplateError",
    "CircularReferenceError",
]
