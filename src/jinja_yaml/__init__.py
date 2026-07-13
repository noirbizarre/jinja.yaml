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

__all__ = [
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
