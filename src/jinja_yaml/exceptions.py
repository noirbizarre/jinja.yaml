"""Exception hierarchy for :mod:`jinja_yaml`.

Every error raised by the library derives from :class:`JinjaYamlError`, so
consumers can catch the whole family with a single ``except`` clause while
still being able to discriminate between the individual failure modes.

All messages are descriptive and actionable, and — where relevant — expose the
offending key path so users can locate the problem in their documents.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    ``existing_locations`` and ``incoming_locations`` contain the contributing
    definitions' coordinates when available.
    """

    def __init__(self, path: KeyPath, message: str | None = None) -> None:
        self.path = path
        self.existing_locations: tuple[SourceLocation, ...] = ()
        self.incoming_locations: tuple[SourceLocation, ...] = ()
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


@dataclass(frozen=True)
class SourceLocation:
    """Optional source metadata, with one-based line and column numbers.

    Coordinates refer to ``source`` when named, otherwise to the value's
    template text. Configuration origins use YAML value-node coordinates;
    template syntax locations remain relative to the template's own text.
    """

    source: str | None = None
    line: int | None = None
    column: int | None = None


class ResolutionError(JinjaYamlError):
    """Resolution failure with structured context for caller-owned formatting.

    ``key_path`` identifies the failing node; ``dependency_chain`` records the
    active resolution path when available. ``location`` can carry source
    metadata without requiring callers to parse the human-readable message.
    ``source_locations`` retains all configuration origins separately from any
    template-relative syntax coordinates in ``location``.
    """

    def __init__(
        self,
        message: str,
        *,
        key_path: KeyPath | None = None,
        dependency_chain: tuple[KeyPath, ...] = (),
        location: SourceLocation | None = None,
    ) -> None:
        self.key_path = key_path
        self.dependency_chain = dependency_chain
        self.location = location
        self.source_locations: tuple[SourceLocation, ...] = ()
        super().__init__(message)


class MissingReferenceError(ResolutionError):
    """An undefined document key, namespace, attribute or item.

    ``reference`` is the missing root name when statically known. For runtime
    lookups it is ``None``; the original Jinja error describes the lookup.
    """

    def __init__(
        self,
        path: KeyPath,
        reference: str | None = None,
        *,
        message: str | None = None,
        dependency_chain: tuple[KeyPath, ...] = (),
        location: SourceLocation | None = None,
    ) -> None:
        self.path = path
        self.reference = reference
        detail = message or f"reference to undefined key or namespace {reference!r}"
        super().__init__(
            f"Missing reference at {format_key_path(path)!r}: {detail}",
            key_path=path,
            dependency_chain=dependency_chain,
            location=location,
        )


class InvalidTemplateError(ResolutionError):
    """Raised when a template cannot be parsed or rendered.

    Wraps the underlying Jinja error and annotates it with the key path of the
    offending node.
    """

    def __init__(
        self,
        path: KeyPath,
        message: str,
        *,
        dependency_chain: tuple[KeyPath, ...] = (),
        location: SourceLocation | None = None,
    ) -> None:
        self.path = path
        super().__init__(
            f"Invalid template at {format_key_path(path)!r}: {message}",
            key_path=path,
            dependency_chain=dependency_chain,
            location=location,
        )


class TemplateEvaluationError(InvalidTemplateError):
    """A template failed during evaluation, including custom filter failures."""


class CircularReferenceError(ResolutionError):
    """Raised when keys reference each other in a cycle.

    The :attr:`path` attribute exposes the ordered cycle of key paths, and the
    string representation renders it as ``a -> b -> c -> a``.
    """

    def __init__(self, cycle: list[KeyPath], *, location: SourceLocation | None = None) -> None:
        self.path = cycle
        rendered = " -> ".join(format_key_path(node) for node in cycle)
        super().__init__(
            f"Circular reference detected: {rendered}",
            key_path=cycle[0] if cycle else None,
            dependency_chain=tuple(cycle),
            location=location,
        )
