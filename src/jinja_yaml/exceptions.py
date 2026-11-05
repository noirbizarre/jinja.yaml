"""Exception hierarchy for :mod:`jinja_yaml`.

Every error raised by the library derives from :class:`JinjaYamlError`, so
consumers can catch the whole family with a single ``except`` clause while
still being able to discriminate between the individual failure modes.

All messages are descriptive and actionable, and — where relevant — expose the
offending key path so users can locate the problem in their documents.
"""

from __future__ import annotations

from .types import KeyPath, format_key_path


class JinjaYamlError(Exception):
    """Base class for every error raised by :mod:`jinja_yaml`."""


class LoadError(JinjaYamlError):
    """Raised when a source cannot be loaded into a document tree."""


class MergeError(JinjaYamlError):
    """Base class for errors occurring while merging documents."""


class DuplicateKeyError(LoadError, MergeError):
    """Raised for repeated YAML keys or conflicting merged values.

    This covers both duplicate keys *within* a single YAML document and
    conflicting leaf values discovered while *merging* several documents.
    Within a YAML mapping, even identical repeated values are rejected.
    """

    def __init__(self, path: KeyPath, message: str | None = None) -> None:
        self.path = path
        location = format_key_path(path)
        super().__init__(message or f"Duplicate key: {location!r} is defined more than once")


class NamespaceCollisionError(JinjaYamlError):
    """Raised when a top-level document key shadows an injected namespace."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Namespace collision: {name!r} is a reserved injected namespace "
            f"and cannot be used as a top-level document key"
        )


class ResolutionError(JinjaYamlError):
    """Base class for failures occurring during template resolution."""


class InvalidTemplateError(ResolutionError):
    """Raised when a template cannot be parsed or rendered.

    Wraps the underlying Jinja error and annotates it with the key path of the
    offending node.
    """

    def __init__(self, path: KeyPath, message: str) -> None:
        self.path = path
        location = format_key_path(path)
        super().__init__(f"Invalid template at {location!r}: {message}")


class CircularReferenceError(ResolutionError):
    """Raised when keys reference each other in a cycle.

    The :attr:`path` attribute exposes the ordered cycle of key paths, and the
    string representation renders it as ``a -> b -> c -> a``.
    """

    def __init__(self, cycle: list[KeyPath]) -> None:
        self.path = cycle
        rendered = " -> ".join(format_key_path(node) for node in cycle)
        super().__init__(f"Circular reference detected: {rendered}")
