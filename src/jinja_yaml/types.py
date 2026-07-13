"""Shared type aliases used across :mod:`jinja_yaml`.

This module intentionally contains no runtime logic. It only declares the
vocabulary of types the library reasons about, so the rest of the codebase can
stay small, explicit and strongly typed.
"""

from __future__ import annotations

from typing import Any

type Scalar = str | int | float | bool | None
"""A leaf value in a document tree."""

type Node = Scalar | list["Node"] | dict[str, "Node"]
"""Any node in a document tree: a scalar, a list or a mapping."""

type Document = dict[str, Node]
"""A logical document: a mapping of top-level keys to nodes."""

type Namespaces = dict[str, Any]
"""Externally injected namespaces made available to templates."""

type KeyPath = tuple[str | int, ...]
"""The location of a node within a document, e.g. ``("network", "hosts", 0)``."""


def format_key_path(path: KeyPath) -> str:
    """Render a :data:`KeyPath` as a human-readable dotted string.

    List indices are rendered with brackets so the result is unambiguous::

        ("network", "hosts", 0)  ->  "network.hosts[0]"
    """
    parts: list[str] = []
    for segment in path:
        if isinstance(segment, int):
            parts.append(f"[{segment}]")
        elif parts:
            parts.append(f".{segment}")
        else:
            parts.append(segment)
    return "".join(parts) if parts else "<root>"
