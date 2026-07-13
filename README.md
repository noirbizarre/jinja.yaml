# jinja.yaml

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
  explicit, actionable errors.

## Installation

```console
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

- `graph.py` — a small, generic directed dependency graph with cycle detection.
- `environment.py` — the configurable Jinja `Environment` (native types,
  strict undefined, custom filters/tests/globals).
- `exceptions.py` — the exception hierarchy.
- `types.py` — shared type aliases.
- `api.py` — the small public API.

### How resolution works

1. The merged document is walked to collect every templated leaf and its key
   path.
2. For each leaf, the referenced top-level keys are discovered **statically**
   from Jinja's AST, and recorded as edges in a dependency graph.
3. Cycles are detected up-front and reported as `CircularReferenceError` with
   the offending path (`a -> b -> c -> a`).
4. Values are resolved **lazily** and **cached**, rendering through a
   `NativeEnvironment` so single-expression values keep their native type. A
   runtime resolution stack acts as a defensive net for dependencies introduced
   by custom filters or globals that static analysis cannot see.

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
