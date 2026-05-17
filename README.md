# Snake Eyes

**Python analyzer for [Gaze](https://github.com/unbound-force/gaze) -- test quality analysis via side effect detection.**

Snake Eyes detects observable side effects in Python functions and reports them to Gaze's universal scoring engine via JSON-RPC. Gaze handles classification, CRAP scoring, reporting, and everything else -- Snake Eyes focuses entirely on understanding Python.

## How It Works

```
gaze analyze --analyzer snake-eyes ./src
```

Gaze spawns Snake Eyes as a subprocess and communicates via JSON-RPC 2.0 over stdin/stdout:

```
     ┌─────────────────────────────────┐
     │         Gaze (Go core)          │
     │                                 │
     │  CLI, TUI, Reports, AI pipeline │
     │  Taxonomy, Classification       │
     │  CRAP scoring, Quadrants        │
     └──────────────┬──────────────────┘
                    │ JSON-RPC stdin/stdout
     ┌──────────────▼──────────────────┐
     │      Snake Eyes (Python)        │
     │                                 │
     │  Side effect detection          │
     │  Coverage parsing               │
     │  Complexity calculation         │
     │  Test-to-assertion mapping      │
     └────────────────────────────────┘
```

Snake Eyes implements Gaze's [external analyzer protocol](https://github.com/unbound-force/gaze/issues/95), providing six JSON-RPC methods:

| Method | Purpose |
|--------|---------|
| `initialize` | Handshake and capability negotiation |
| `discover` | Find Python source and test files |
| `analyze` | Detect side effects per function |
| `complexity` | Cyclomatic complexity per function |
| `coverage` | Parse coverage.py data |
| `shutdown` | Clean process exit |

Future methods (`test_mapping`, `classify_signals`) will enable full test quality assessment and contract classification.

## What It Detects

Snake Eyes detects Python-specific side effects and reports them using Gaze's [universal taxonomy](https://github.com/unbound-force/gaze/issues/96):

| Tier | Effects |
|------|---------|
| **P0** Must Detect | Return values, raised exceptions, `self` attribute mutations, mutable argument mutations |
| **P1** High Value | Global/module-level mutations, `print()`/stdout writes, `yield`/`yield from`, container mutations (list/dict/set) |
| **P2** Important | File I/O, database writes, subprocess/thread spawning, logging, decorator mutations, descriptor protocol, context manager effects, monkey-patching, async generator yields |

Detection uses Python's `ast` and `symtable` modules for structural analysis, with [Astroid](https://github.com/pylint-dev/astroid) for name resolution, type inference, and cross-module import resolution.

## Installation

```bash
pip install snake-eyes
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install snake-eyes
```

Snake Eyes requires Python 3.11+ and a working [Gaze](https://github.com/unbound-force/gaze) installation.

## Configuration

Configure Snake Eyes as an analyzer in your project's `.gaze.yaml`:

```yaml
analyzers:
  python:
    command: snake-eyes
    args: ["--stdio"]
```

## Project Status

Snake Eyes is in early development (v0.x). It is part of the [zero-dot-force](https://github.com/zero-dot-force) labs organization -- the experimental incubator for [Unbound Force](https://github.com/unbound-force).

### Roadmap

- **v0.1** -- P0 side effect detection, CRAP score support (complexity + coverage), basic CLI
- **v0.2** -- P1 effects, test-to-assertion mapping, classification signals
- **v0.3** -- P2 effects, full test quality assessment

### Related Issues on Gaze

- [#95 -- External analyzer protocol](https://github.com/unbound-force/gaze/issues/95)
- [#96 -- Universal taxonomy](https://github.com/unbound-force/gaze/issues/96)

## Architecture

```
snake-eyes/
├── src/snake_eyes/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (snake-eyes --stdio)
│   ├── server.py            # JSON-RPC server (stdin/stdout)
│   ├── protocol.py          # Request/response types
│   ├── discovery.py         # File discovery (source + tests)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── detector.py      # Side effect detection (ast + symtable)
│   │   ├── inference.py     # Name/type resolution (astroid)
│   │   ├── effects.py       # Effect type definitions
│   │   └── patterns.py      # Known I/O and mutation patterns
│   ├── complexity.py        # Cyclomatic complexity (radon)
│   └── coverage.py          # coverage.py data parsing
├── tests/
├── pyproject.toml
└── .gaze.yaml
```

## Dependencies

| Dependency | Purpose |
|------------|---------|
| [astroid](https://github.com/pylint-dev/astroid) | Name resolution, type inference, cross-module imports |
| [radon](https://github.com/rubik/radon) | Cyclomatic complexity computation |
| [coverage](https://github.com/nedbat/coveragepy) | Coverage data parsing |

Python's `ast` and `symtable` modules (stdlib) provide the primary parsing and scope analysis.

## License

Apache 2.0 -- see [LICENSE](LICENSE).
