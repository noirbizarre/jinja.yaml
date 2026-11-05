"""The Jinja environment used to parse and render templated values.

A dedicated :class:`Environment` subclasses Jinja's
:class:`~jinja2.nativetypes.NativeEnvironment`, which returns native Python
types when a template consists of a single expression (so ``"{{ port }}"``
yields an ``int`` rather than a ``str``). It defaults to
:class:`~jinja2.StrictUndefined` so that references to unknown keys fail loudly.

The environment is the extension point of the library: custom filters, tests,
globals and functions can be injected without touching the resolver.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jinja2 import StrictUndefined, Undefined
from jinja2.nativetypes import NativeEnvironment

from ._analysis import TemplateAnalysis

__all__ = ["Environment"]

_BLOCK_MARKERS = ("{{", "{%", "{#")


class Environment(NativeEnvironment):
    """The configurable Jinja environment used by the resolver.

    Parameters mirror the common extension points. Anything else supported by
    :class:`jinja2.Environment` can be passed through ``**options``.
    """

    def __init__(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        tests: Mapping[str, Any] | None = None,
        globals: Mapping[str, Any] | None = None,
        undefined: type[Undefined] = StrictUndefined,
        **options: Any,
    ) -> None:
        super().__init__(undefined=undefined, **options)
        if filters:
            self.filters.update(filters)
        if tests:
            self.tests.update(tests)
        if globals:
            self.globals.update(globals)

    def is_template(self, value: str) -> bool:
        """Return whether ``value`` contains any Jinja construct."""
        return any(marker in value for marker in _BLOCK_MARKERS)

    def referenced_variables(self, source: str) -> set[str]:
        """Return the set of undeclared (root) variables referenced by ``source``.

        This is a *static* analysis performed on the parsed AST; the template is
        not rendered. Dotted access such as ``data.domain`` surfaces its root
        (``data``). Static loader references are followed with Jinja's context
        rules; dynamic targets cannot contribute additional dependencies.
        """
        return TemplateAnalysis(self).variables(source)
