"""Merging phase: combine several raw documents into one logical document.

Mappings merge recursively; lists and scalars are atomic leaves. The default
``strict`` strategy accepts Python-equal leaves and rejects conflicting values.
The ``override`` strategy replaces leaves and incompatible categories with the
later source's value. Both strategies operate before template resolution.
"""

from __future__ import annotations

from collections.abc import Iterable

from .exceptions import DuplicateKeyError
from .provenance import _annotate_duplicate, _SourceDocument
from .types import Document, KeyPath, MergeStrategy, Node

__all__ = ["merge"]


def merge(documents: Iterable[Document], *, merge_strategy: MergeStrategy = "strict") -> Document:
    """Merge without mutating inputs; optionally let later sources override.

    Mappings merge recursively. Lists are never concatenated or merged by index.
    Strict merging retains the first Python-equal leaf; override retains the last.
    Unknown strategies raise :class:`ValueError`, even for empty input.
    """
    return _merge(
        (_SourceDocument(document) for document in documents), merge_strategy=merge_strategy
    ).data


def _validate_merge_strategy(merge_strategy: MergeStrategy) -> None:
    if merge_strategy not in ("strict", "override"):
        msg = f"Unknown merge strategy {merge_strategy!r}; expected 'strict' or 'override'"
        raise ValueError(msg)


def _merge(
    documents: Iterable[_SourceDocument], *, merge_strategy: MergeStrategy = "strict"
) -> _SourceDocument:
    _validate_merge_strategy(merge_strategy)
    result = _SourceDocument({})
    for document in documents:
        _merge_into(
            result.data,
            document.data,
            path=(),
            target_document=result,
            source=document,
            merge_strategy=merge_strategy,
        )
        for path, locations in document.origins.items():
            result.origins[path] = (*result.origins.get(path, ()), *locations)
    return result


def _copy_node(node: Node) -> Node:
    # Copy each structural occurrence: deepcopy would preserve alias sharing.
    if isinstance(node, dict):
        return {key: _copy_node(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_copy_node(value) for value in node]
    return node


def _discard_origins(document: _SourceDocument, node: Node, path: KeyPath) -> None:
    """Remove a discarded subtree's origins without scanning unrelated paths."""
    if not document.origins:
        return
    pending = [(path, node)]
    while pending:
        node_path, current = pending.pop()
        document.origins.pop(node_path, None)
        if isinstance(current, dict):
            pending.extend(((*node_path, key), value) for key, value in current.items())
        elif isinstance(current, list):
            pending.extend(((*node_path, index), value) for index, value in enumerate(current))


def _merge_into(
    target: dict[str, Node],
    incoming: dict[str, Node],
    *,
    path: KeyPath,
    target_document: _SourceDocument,
    source: _SourceDocument,
    merge_strategy: MergeStrategy,
) -> None:
    for key, value in incoming.items():
        key_path = (*path, key)
        if key not in target:
            target[key] = _copy_node(value)
            continue

        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_into(
                existing,
                value,
                path=key_path,
                target_document=target_document,
                source=source,
                merge_strategy=merge_strategy,
            )
        elif merge_strategy == "override":
            target[key] = _copy_node(value)
            # Discard the entire old subtree's attribution before incoming
            # origins are accumulated, including now-nonexistent list indices.
            _discard_origins(target_document, existing, key_path)
        elif existing == value:
            # Identical redefinition is harmless and therefore allowed.
            continue
        else:
            raise _annotate_duplicate(
                DuplicateKeyError(key_path),
                target_document.origins.get(key_path, ()),
                source.origins.get(key_path, ()),
            )
