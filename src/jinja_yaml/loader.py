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

from yaml.constructor import ConstructorError

from .exceptions import DuplicateKeyError, LoadError
from .types import Document, KeyPath, Node, format_key_path

__all__ = ["StrictSafeLoader", "load_mapping", "load_path", "load_paths"]


class StrictSafeLoader(yaml.SafeLoader):
    """A safe loader for string-keyed, nonrecursive document trees."""

    origin: str = "<YAML input>"

    def _location(self, node: yaml.Node, path: KeyPath) -> str:
        mark = node.start_mark
        return (
            f"{self.origin}, line {mark.line + 1}, column {mark.column + 1} "
            f"at {format_key_path(path)!r}"
        )

    def construct_document(self, node: yaml.Node) -> Any:
        if node.tag not in {"tag:yaml.org,2002:map", "tag:yaml.org,2002:null"}:
            raise LoadError(f"Expected a mapping at the top level of {self._location(node, ())}")
        self._validate(node, (), set())
        return super().construct_document(node)

    def _validate(self, node: yaml.Node, path: KeyPath, active: set[int]) -> None:
        location = self._location(node, path)
        if id(node) in active:
            raise LoadError(f"Recursive YAML structure in {location}")
        active.add(id(node))
        try:
            if isinstance(node, yaml.MappingNode) and node.tag == "tag:yaml.org,2002:map":
                self._validate_mapping(node, path, active)
            elif isinstance(node, yaml.SequenceNode) and node.tag == "tag:yaml.org,2002:seq":
                for index, item in enumerate(node.value):
                    self._validate(item, (*path, index), active)
            elif isinstance(node, yaml.ScalarNode) and node.tag in {
                f"tag:yaml.org,2002:{kind}" for kind in ("str", "int", "float", "bool", "null")
            }:
                try:
                    self.construct_object(node)
                except (ValueError, OverflowError, KeyError, IndexError) as error:
                    raise ConstructorError(
                        None, None, f"Invalid scalar in {location}: {error}", node.start_mark
                    ) from error
            else:
                raise ConstructorError(
                    None, None, f"Unsupported YAML type {node.tag!r} in {location}", node.start_mark
                )
        finally:
            active.remove(id(node))

    def _validate_mapping(self, node: yaml.MappingNode, path: KeyPath, active: set[int]) -> None:
        seen: dict[str, yaml.Node] = {}
        for key, value in node.value:
            if key.tag == "tag:yaml.org,2002:merge":
                raise LoadError(
                    f"YAML merge keys (<<) are unsupported in {self._location(key, path)}"
                )
            if not isinstance(key, yaml.ScalarNode) or key.tag != "tag:yaml.org,2002:str":
                raise LoadError(
                    f"Mapping keys must be strings in {self._location(key, path)} (got {key.tag})"
                )
            child_path = (*path, key.value)
            if key.value in seen:
                first = seen[key.value].start_mark
                raise DuplicateKeyError(
                    child_path,
                    f"Duplicate key in {self._location(key, child_path)}; "
                    f"first defined at line {first.line + 1}, column {first.column + 1}",
                )
            seen[key.value] = key
            self._validate(value, child_path, active)


def _parse(text: str, *, origin: str) -> Document:
    loader: StrictSafeLoader | None = None
    try:
        loader = StrictSafeLoader(text)
        loader.origin = origin
        data = loader.get_single_data()
    except yaml.YAMLError as error:
        raise LoadError(f"Failed to parse YAML from {origin}: {error}") from error
    finally:
        if loader is not None:
            loader.dispose()

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
    except (OSError, UnicodeError) as error:
        raise LoadError(f"Failed to read {str(path)!r}: {error}") from error
    return _parse(text, origin=str(path))


def load_paths(paths: Iterable[str | Path]) -> list[Document]:
    """Load several YAML files into a list of raw document trees."""
    return [load_path(path) for path in paths]


def load_mapping(data: dict[str, Any]) -> Document:
    """Adopt an in-memory mapping as a raw document tree.

    The mapping is deep-copied so callers never observe mutations, and its keys
    and values are validated against the supported document types.
    """
    if not isinstance(data, dict):
        raise LoadError(f"Expected a mapping, got {type(data).__name__}")
    return _copy_mapping(data, (), set())


def _copy_mapping(data: dict[str, Any], path: KeyPath, active: set[int]) -> Document:
    if id(data) in active:
        raise LoadError(f"Recursive in-memory mapping at {format_key_path(path)!r}")
    active.add(id(data))
    try:
        result: Document = {}
        for key, value in data.items():
            if not isinstance(key, str):
                raise LoadError(
                    f"Mapping keys must be strings at {format_key_path(path)!r} "
                    f"in in-memory mapping, got {type(key).__name__}: {key!r}"
                )
            result[key] = _copy_node(value, (*path, key), active)
        return result
    finally:
        active.remove(id(data))


def _copy_node(value: Any, path: KeyPath, active: set[int]) -> Node:
    if isinstance(value, dict):
        return _copy_mapping(value, path, active)
    if isinstance(value, list):
        if id(value) in active:
            raise LoadError(f"Recursive in-memory list at {format_key_path(path)!r}")
        active.add(id(value))
        try:
            return [_copy_node(item, (*path, index), active) for index, item in enumerate(value)]
        finally:
            active.remove(id(value))
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise LoadError(
        f"Unsupported value type {type(value).__name__} at {format_key_path(path)!r} "
        "in in-memory mapping"
    )
