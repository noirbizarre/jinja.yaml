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
from .types import Document, KeyPath, Node

__all__ = ["merge"]


def merge(documents: Iterable[Document]) -> Document:
    """Deep-merge a sequence of documents into a single logical document."""
    result: Document = {}
    for document in documents:
        _merge_into(result, document, path=())
    return result


def _merge_into(target: dict[str, Node], source: dict[str, Node], *, path: KeyPath) -> None:
    for key, value in source.items():
        key_path = (*path, key)
        if key not in target:
            target[key] = value
            continue

        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_into(existing, value, path=key_path)
        elif existing == value:
            # Identical redefinition is harmless and therefore allowed.
            continue
        else:
            raise DuplicateKeyError(key_path)
