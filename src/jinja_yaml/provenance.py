"""Private source-aware documents used between pipeline phases."""

from __future__ import annotations

from dataclasses import dataclass, field

from .exceptions import DuplicateKeyError, ResolutionError, SourceLocation
from .types import KeyPath

type _Provenance = dict[KeyPath, tuple[SourceLocation, ...]]


@dataclass
class _SourceDocument[Data]:
    """Keep source metadata with its tree until the public API unwraps it."""

    data: Data
    origins: _Provenance = field(default_factory=dict)


def _format_locations(locations: tuple[SourceLocation, ...]) -> str:
    parts = []
    for location in locations:
        text = location.source or "<unknown source>"
        if location.line is not None:
            text += f", line {location.line}"
        if location.column is not None:
            text += f", column {location.column}"
        parts.append(text)
    return "; ".join(parts)


def _annotate_resolution(
    error: ResolutionError,
    locations: tuple[SourceLocation, ...],
) -> ResolutionError:
    """Annotate only errors created by this pipeline, retaining template marks."""
    error.source_locations = locations
    if locations:
        if error.location is None:
            error.location = locations[0]
        error.args = (f"{error} (configuration source: {_format_locations(locations)})",)
    return error


def _annotate_duplicate(
    error: DuplicateKeyError,
    existing: tuple[SourceLocation, ...],
    incoming: tuple[SourceLocation, ...],
) -> DuplicateKeyError:
    error.existing_locations = existing
    error.incoming_locations = incoming
    details = []
    if existing:
        details.append(f"existing source: {_format_locations(existing)}")
    if incoming:
        details.append(f"incoming source: {_format_locations(incoming)}")
    if details:
        error.args = (f"{error} ({'; '.join(details)})",)
    return error
