"""Merging phase: combine several raw documents into one logical document.

Once loaded, the library never reasons about files: the order in which sources
are provided must not affect the result. Nested mappings are merged
recursively; lists and scalars are treated as leaves. A conflict on a leaf —
the same path defined with different values — raises a
:class:`~jinja_yaml.exceptions.DuplicateKeyError`.

Defining the same leaf with the *same* value in two sources is allowed: it is
unambiguous and cannot surprise the user.
"""

from __future__ import annotations

from collections.abc import Iterable

from .exceptions import DuplicateKeyError
from .provenance import _annotate_duplicate, _SourceDocument
from .types import Document, KeyPath, Node

__all__ = ["merge"]


def merge(documents: Iterable[Document]) -> Document:
    """Deep-merge a sequence of documents into a single logical document."""
    return _merge(_SourceDocument(document) for document in documents).data


def _merge(documents: Iterable[_SourceDocument]) -> _SourceDocument:
    result = _SourceDocument({})
    for document in documents:
        _merge_into(result.data, document.data, path=(), target_document=result, source=document)
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


def _merge_into(
    target: dict[str, Node],
    incoming: dict[str, Node],
    *,
    path: KeyPath,
    target_document: _SourceDocument,
    source: _SourceDocument,
) -> None:
    for key, value in incoming.items():
        key_path = (*path, key)
        if key not in target:
            target[key] = _copy_node(value)
            continue

        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_into(
                existing, value, path=key_path, target_document=target_document, source=source
            )
        elif existing == value:
            # Identical redefinition is harmless and therefore allowed.
            continue
        else:
            raise _annotate_duplicate(
                DuplicateKeyError(key_path),
                target_document.origins.get(key_path, ()),
                source.origins.get(key_path, ()),
            )
