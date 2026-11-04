"""Loading phase: turn input sources into raw document trees.

The loader knows how to read YAML from a single file, several files or an
in-memory mapping. It performs no template resolution and no cross-document
merging — it only produces raw :data:`~jinja_yaml.types.Document` trees.

Duplicate keys *within a single YAML mapping* are rejected here, because PyYAML
would otherwise silently keep the last occurrence.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
import yaml.resolver

from .exceptions import DuplicateKeyError, LoadError
from .types import Document

__all__ = ["StrictSafeLoader", "load_mapping", "load_path", "load_paths"]


class StrictSafeLoader(yaml.SafeLoader):
    """A :class:`yaml.SafeLoader` that rejects duplicate mapping keys."""


def _construct_mapping(loader: StrictSafeLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise DuplicateKeyError((str(key),))
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _parse(text: str, *, origin: str) -> Document:
    try:
        data = yaml.load(text, Loader=StrictSafeLoader)
    except DuplicateKeyError:
        raise
    except yaml.YAMLError as error:
        raise LoadError(f"Failed to parse YAML from {origin}: {error}") from error

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise LoadError(
            f"Expected a mapping at the top level of {origin}, got {type(data).__name__}"
        )
    return data


def load_path(path: str | Path) -> Document:
    """Load a single YAML file into a raw document tree."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise LoadError(f"Failed to read {str(path)!r}: {error}") from error
    return _parse(text, origin=str(path))


def load_paths(paths: Iterable[str | Path]) -> list[Document]:
    """Load several YAML files into a list of raw document trees."""
    return [load_path(path) for path in paths]


def load_mapping(data: dict[str, Any]) -> Document:
    """Adopt an in-memory mapping as a raw document tree.

    The mapping is deep-copied so callers never observe mutations, and its keys
    are validated to be strings.
    """
    if not isinstance(data, dict):
        raise LoadError(f"Expected a mapping, got {type(data).__name__}")
    return _copy_mapping(data)


def _copy_mapping(data: dict[str, Any]) -> Document:
    result: Document = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise LoadError(f"Mapping keys must be strings, got {type(key).__name__}: {key!r}")
        result[key] = _copy_node(value)
    return result


def _copy_node(value: Any) -> Any:
    if isinstance(value, dict):
        return _copy_mapping(value)
    if isinstance(value, list):
        return [_copy_node(item) for item in value]
    return value
