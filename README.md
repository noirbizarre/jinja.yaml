<!-- markdownlint-disable MD013 MD033 MD041 -->
<p align="center">
  <img src="docs/images/icon.svg" alt="jinja.yaml" width="160">
</p>

<h1 align="center">jinja.yaml</h1>

<p align="center"><strong>YAML configuration with dependency-aware Jinja templating</strong></p>

<p align="center">
  <a href="https://github.com/noirbizarre/jinja.yaml/actions/workflows/ci.yaml">
    <img src="https://github.com/noirbizarre/jinja.yaml/actions/workflows/ci.yaml/badge.svg" alt="CI">
  </a>
  <a href="https://codecov.io/gh/noirbizarre/jinja.yaml">
    <img src="https://codecov.io/gh/noirbizarre/jinja.yaml/graph/badge.svg" alt="Codecov">
  </a>
  <a href="https://pypi.org/project/jinja.yaml/">
    <img src="https://img.shields.io/pypi/v/jinja.yaml" alt="PyPI">
  </a>
  <img src="https://img.shields.io/github/v/release/noirbizarre/jinja.yaml" alt="Release">
  <a href="https://github.com/j178/prek">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json" alt="prek">
  </a>
  <img src="https://img.shields.io/github/license/noirbizarre/jinja.yaml" alt="License">
</p>

<!-- markdownlint-enable MD013 MD033 MD041 -->

---

<!-- One paragraph: what this does and why it exists. Lead with the problem, -->
YAML configuration with dependency-aware Jinja templating.

`jinja.yaml` loads one or more YAML documents containing [Jinja2][jinja]
expressions, merges them into a single logical document, and resolves the
references between keys — regardless of the order in which they are declared.

```yaml
domain: home.arpa
fqdn: "nas.{{ domain }}"
```

```python
from jinja_yaml import load_file

load_file("config.jinja.yaml")
# {"domain": "home.arpa", "fqdn": "nas.home.arpa"}
```

## Motivation

Configuration often contains values derived from other values: a fully-qualified
domain name built from a base domain, a connection string assembled from a host
and a port, a URL composed of several parts. Expressing these relationships by
hand is repetitive and error-prone.

`jinja.yaml` lets you express them as templates and resolves them for you. It is
a **generic library**: it knows nothing about hosts, inventories, environments
or any other domain-specific concept. Those belong to the consumers of the
library, which can inject them as [namespaces](#external-namespaces).

Key properties:

- **Declaration-order independent** — a key may reference another key defined
  later in the document.
- **Dependency-aware** — references are discovered statically and resolved
  lazily through a dependency graph, with caching.
- **Type-preserving** — a value that is a single expression keeps its native
  type (`int`, `list`, `dict`, ...).
- **Strict** — missing references, duplicate keys and circular references raise

<!-- not the implementation. -->

## Installation

```Shell
pip install jinja.yaml
```

Requires Python 3.12 or later.

## Quick start

```python
from jinja_yaml import load, load_dict, load_file, load_files

# From a single file
config = load_file("config.jinja.yaml")

# From several files, merged into one logical document
config = load_files(["base.jinja.yaml", "overrides.jinja.yaml"])

# From an in-memory mapping
config = load_dict({"fqdn": "nas.{{ domain }}", "domain": "home.arpa"})

# `load` dispatches on the type of its argument
config = load("config.jinja.yaml")
config = load(["base.jinja.yaml", "overrides.jinja.yaml"])
config = load({"key": "{{ other }}", "other": "value"})
```

Every function returns a fully-resolved plain `dict`.

> [!TIP]
> Any file extension works, but we recommend `.jinja.yaml` (e.g.
> `config.jinja.yaml`): it makes the templated nature of the file explicit and
> enables proper syntax highlighting in most editors.

## Examples

### Declaration order does not matter

```python
load_dict({"fqdn": "nas.{{ domain }}", "domain": "home.arpa"})
# {"fqdn": "nas.home.arpa", "domain": "home.arpa"}

load_dict({"domain": "home.arpa", "fqdn": "nas.{{ domain }}"})
# {"fqdn": "nas.home.arpa", "domain": "home.arpa"}
```

### Nested structures and dotted access

```python
load_dict(
    {
        "net": {"domain": "home.arpa"},
        "url": "https://{{ net.domain }}",
        "hosts": ["{{ net.domain }}", "www.{{ net.domain }}"],
    }
)
# {
#     "net": {"domain": "home.arpa"},
#     "url": "https://home.arpa",
#     "hosts": ["home.arpa", "www.home.arpa"],
# }
```

### Native types are preserved

A value consisting of a single expression keeps the referenced value's type:

```python
load_dict({"port": "{{ base }}", "base": 8080})
# {"port": 8080, "base": 8080}    <- port is an int, not "8080"
```

### External namespaces

The loader accepts externally injected namespaces. Templates may reference them,
but the library itself knows nothing about their meaning:

```python
import os

load_dict(
    {"url": "https://{{ data.domain }}", "user": "{{ env.USER }}"},
    namespaces={"data": {"domain": "example.com"}, "env": os.environ},
)
```

Namespace names are reserved: defining a top-level key that shadows an injected
namespace raises `NamespaceCollisionError`.

### Custom filters, tests and globals

The Jinja environment is configurable and is the single extension point:

```python
from jinja_yaml import Environment, load_dict

env = Environment(
    filters={"shout": str.upper},
    globals={"answer": 42},
)
load_dict({"x": "{{ 'hi' | shout }}-{{ answer }}"}, environment=env)
# {"x": "HI-42"}
```

### Errors

```python
from jinja_yaml import CircularReferenceError, load_dict

try:
    load_dict({"a": "{{ b }}", "b": "{{ c }}", "c": "{{ a }}"})
except CircularReferenceError as error:
    print(error)
# Circular reference detected: a -> b -> c -> a
```

#### Resolution diagnostics

All resolution failures derive from `ResolutionError` (and `JinjaYamlError`):

- `MissingReferenceError`: an unknown root key/namespace or an undefined nested
  attribute/item. `.reference` contains the missing root name when statically
  known, otherwise `None`.
- `InvalidTemplateError`: invalid syntax or failed static template analysis.
- `TemplateEvaluationError`: evaluation failed, including Python exceptions from
  filters, globals, or template operators. Also an `InvalidTemplateError`.
- `CircularReferenceError`: a dependency cycle; `.path` is the ordered, closed
  list of key paths, such as `[("a",), ("b",), ("a",)]`.

Errors expose `.key_path` (the failing key as a tuple), `.dependency_chain`
(a tuple of active key paths, or the closed cycle), and optional `.location`
metadata. Static analysis failures have no active resolution chain. These fields
let applications build their own diagnostics without parsing exception messages:

```python
from jinja_yaml import MissingReferenceError, load_dict

try:
    load_dict({"url": "{{ host }}", "host": "{{ domain }}"})
except MissingReferenceError as error:
    print(error)
    print(error.key_path, error.reference, error.dependency_chain)
# Missing reference at 'host': reference to undefined key or namespace 'domain'
# ('host',) domain (('url',), ('host',))
```

Wrapped failures retain the original exception in `error.__cause__`. Statically
detected missing roots and configuration cycles have no underlying exception.
Syntax errors include a `SourceLocation` with a one-based `.line` and, for
loader-backed templates, `.source` when available. `.column` is optional. These
coordinates describe template text, not the YAML file: YAML source metadata is
not yet retained through merging and resolution. Errors accept optional source
locations so future metadata can be attached without changing diagnostic fields.

#### Loading and validation errors

Input documents must be mappings with string keys at every depth. Values may
be nested mappings, lists, strings, integers, floats, booleans, or nulls. Empty
files and explicit YAML null documents (`null` or `~`) load as empty mappings.
Other top-level values, including lists, are rejected.

These rules also apply to `load_dict`, which copies its input without mutating
it. Dates/timestamps, binary data, sets, tuples, arbitrary Python objects, and
unsupported YAML tags are rejected. Quote date-like values such as
`"2026-01-01"` to keep them as strings. Nonrecursive YAML aliases and shared
in-memory containers are accepted; recursive structures are rejected. YAML
merge keys (`<<`) are unsupported; a quoted `"<<"` is an ordinary string key.
Validation here concerns loaded document data, not injected namespaces or
values produced by template evaluation.

Repeated keys within a YAML mapping raise `DuplicateKeyError`, even when their
values are identical. Its `.path` identifies the full nested key, including
list indices. When merging separate documents, identical leaf values are
allowed, but conflicting values raise `DuplicateKeyError`.

File-reading failures, invalid YAML, and unsupported document shapes raise
`LoadError` (`DuplicateKeyError` is also a `LoadError`). File errors identify
the source filename; validation errors include a logical key path and, when
available, one-based line and column numbers. Duplicate errors also identify
the first definition. Alias diagnostics use the anchor's definition location.
In-memory errors identify the logical path without source coordinates.
Underlying parser, filesystem, and decoding exceptions are preserved as
`error.__cause__`.

```python
from jinja_yaml import LoadError, load_file

try:
    load_file("config.jinja.yaml")
except LoadError as error:
    print(error)
# For a repeated key, for example:
# Duplicate key in config.jinja.yaml, line 3, column 5 at 'items[0].key'; first defined at line 2, column 5
```

## Architecture

The library operates in four independent phases, each backed by a focused
module under `src/jinja_yaml/`:

| Phase        | Module           | Responsibility |
|--------------|------------------|----------------|
| **Load**     | `loader.py`      | Read YAML (file, files or mapping) into raw document trees. Rejects duplicate keys within a document. |
| **Merge**    | `merger.py`      | Deep-merge several documents into one logical document. File names and order never affect the result. |
| **Resolve**  | `resolver.py`    | Evaluate templated values against the merged document. |
| **Validate** | *(future)*       | Optional schema validation. The architecture is designed to accommodate it without a redesign. |

Supporting modules:

- `graph.py` — a generic dependency graph using `graphlib` for dependency-first
  ordering and cycle detection.
- `environment.py` — the configurable Jinja `Environment` (native types,
  strict undefined, custom filters/tests/globals).
- `exceptions.py` — the exception hierarchy.
- `types.py` — shared type aliases.
- `api.py` — the small public API.

### How resolution works

1. The merged document is walked to collect every value and its key path.
2. For each leaf, the referenced top-level keys are discovered **statically**
   using Jinja's metadata analysis, and recorded as edges in a dependency graph.
   Containers also depend on their immediate children. An edge `a -> b` means
   that `a` depends on `b`.
3. Cycles are detected up-front and reported as `CircularReferenceError` with
   a deterministic closed path (`a -> b -> c -> a`), including nested keys and
   list indices where applicable.
4. Values are resolved **lazily** and **cached**, rendering through a
   `NativeEnvironment` so single-expression values keep their native type. A
   runtime resolution stack acts as a defensive net for dependencies introduced
   by custom filters or globals that static analysis cannot see.

### Static template analysis and its limits

References use **whole-root resolution**: `{{ settings.host }}` depends on the
entire `settings` mapping, including every child. A field referencing a sibling
through its own root therefore remains circular. Injected namespaces and Jinja
environment globals are not configuration graph nodes.

Configure a Jinja loader that provides template source to discover dependencies
in statically named templates:

```python
from jinja2 import DictLoader
from jinja_yaml import Environment, load_dict

env = Environment(loader=DictLoader({"message": "Hello {{ name }}!"}))
result = load_dict(
    {"greeting": '{% include "message" %}', "name": "world"},
    environment=env,
)
assert result["greeting"] == "Hello world!"
```

Static `include`, `import`, `from ... import`, and `extends` references are
followed transitively. Includes share context by default; imports do not.
Explicit `with context` and `without context` are respected, and caller-local
variables (such as loop variables or preceding assignments) do not become
configuration dependencies. Include fallback lists use the first available
template; missing includes with `ignore missing` contribute no dependencies.
Analysis results are reused when constructing each value's render context.

Analysis is conservative, not execution-path-aware: references in untaken
branches and overridden parent blocks can still introduce dependencies or
missing-key errors. Required static templates are checked before rendering;
missing templates and invalid syntax report the owning configuration path.
Recursive static template-reference chains are unsupported and report the
template chain rather than recursing indefinitely during analysis.

Dynamic references such as `{% include template_name %}` retain Jinja's runtime
behavior. The name expression is analyzed, but additional variables used only
inside the selected template are **not** discovered automatically. Such targets
can use Jinja globals or context already supplied by the caller; otherwise they
may fail at render time. Runtime dependency discovery is not provided.

## Roadmap

- Optional schema validation (the `Validate` phase).
- A richer `Document` return type exposing raw data and the dependency graph,
  alongside the current plain-`dict` API.
- Dependency graph inspection and visualisation helpers.

## Development

The project uses [uv][uv] for dependency management, [mise][mise] for task
automation, [Ruff][ruff] for linting and formatting, [ty][ty] for type
checking, and [prek][prek] for pre-commit hooks.

```console
# Install the toolchain and dependencies
mise install

# Run the test suite
mise run test

# Run the test suite with coverage
mise run cover

# Lint (Ruff + hooks) and type-check
mise run lint
mise run typing

# Format the code
mise run format

# Run the full quality gate (lint + typing + tests)
mise run check
```

Commits follow the [Conventional Commits][conventional] specification, enforced
via [Commitizen][commitizen] with the [Emotional][emotional] plugin.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Released under the [MIT License](LICENSE).

[jinja]: https://jinja.palletsprojects.com/
[uv]: https://docs.astral.sh/uv/
[mise]: https://mise.jdx.dev/
[ruff]: https://docs.astral.sh/ruff/
[ty]: https://docs.astral.sh/ty/
[prek]: https://github.com/j178/prek
[commitizen]: https://commitizen-tools.github.io/commitizen/
[emotional]: https://github.com/noirbizarre/emotional
[conventional]: https://www.conventionalcommits.org/
