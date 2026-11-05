"""The public API of :mod:`jinja_yaml`.

These functions are thin compositions of the four phases — load, merge,
resolve — and return a fully-resolved plain :class:`dict`. The internals are
structured so a richer return type could be introduced later without breaking
this surface.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from . import loader
from .environment import Environment
from .exceptions import LoadError
from .merger import _merge
from .provenance import _SourceDocument
from .resolver import _resolve
from .types import Document, MappingClass, Namespaces

__all__ = ["load", "load_dict", "load_file", "load_files"]


def load_file(
    path: str | Path,
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
    mapping_cls: MappingClass = dict,
) -> Document:
    """Load and resolve a single YAML file."""
    document = loader._load_path(path)
    return _resolve(
        document, namespaces=namespaces, environment=environment, mapping_cls=mapping_cls
    ).data


def load_files(
    paths: Iterable[str | Path],
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
    mapping_cls: MappingClass = dict,
) -> Document:
    """Load, merge and resolve several YAML files as one logical document."""
    documents = [loader._load_path(path) for path in paths]
    merged = _merge(documents)
    return _resolve(
        merged, namespaces=namespaces, environment=environment, mapping_cls=mapping_cls
    ).data


def load_dict(
    data: dict[str, Any],
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
    mapping_cls: MappingClass = dict,
) -> Document:
    """Resolve an in-memory mapping. The input is never mutated."""
    document = _SourceDocument(loader.load_mapping(data))
    return _resolve(
        document, namespaces=namespaces, environment=environment, mapping_cls=mapping_cls
    ).data


def load(
    source: str | Path | Iterable[str | Path] | dict[str, Any],
    *,
    namespaces: Namespaces | None = None,
    environment: Environment | None = None,
    mapping_cls: MappingClass = dict,
) -> Document:
    """Load and resolve a source, dispatching on its type.

    ``source`` may be a path (``str`` or :class:`~pathlib.Path`), an iterable of
    paths, or an in-memory mapping.
    """
    if isinstance(source, dict):
        return load_dict(
            cast("dict[str, Any]", source),
            namespaces=namespaces,
            environment=environment,
            mapping_cls=mapping_cls,
        )
    if isinstance(source, (str, Path)):
        return load_file(
            source, namespaces=namespaces, environment=environment, mapping_cls=mapping_cls
        )
    if isinstance(source, Iterable):
        return load_files(
            source, namespaces=namespaces, environment=environment, mapping_cls=mapping_cls
        )
    raise LoadError(f"Unsupported source type: {type(source).__name__}")
