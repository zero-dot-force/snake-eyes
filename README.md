# Snake Eyes

**Python analyzer backend for [Gaze](https://github.com/unbound-force/gaze).**

Snake Eyes is a Gaze-spawned subprocess. It speaks JSON-RPC 2.0 over stdin/stdout
(protocol v1.1.0). Gaze owns the CLI, scoring, and reports.

## Current status (v0.1.0)

| Method | Status |
|--------|--------|
| `initialize` | Implemented |
| `shutdown` | Implemented |
| `discover` | Implemented |
| `analyze` | Implemented |
| `complexity` | Implemented |
| `coverage` | Implemented |

Capability flags advertised at handshake: `discover` is `true`;
`test_mapping`, `classify_signals`, and `streaming` are `false`.
Side-effect detection is implemented. `coverage.py>=7.0,<8` is a
runtime dependency (shipped). Astroid (name inference) is planned for
a later issue. `radon` is not used — cyclomatic complexity is computed
via a lifted McCabe implementation (no radon dependency).

## Installation

From a clone (not published to PyPI):

```bash
uv sync
uv run snake-eyes --stdio
```

Requires Python 3.11+.

## Configuration

Point Gaze at the local entry point in `.gaze.yaml`:

```yaml
analyzers:
  python:
    command: snake-eyes
    args: ["--stdio"]
```

## Project structure

```
snake-eyes/
├── src/snake_eyes/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (snake-eyes --stdio)
│   ├── server.py            # JSON-RPC server (stdin/stdout)
│   ├── protocol.py          # Request/response types
│   ├── discovery.py         # File discovery (os.walk)
│   ├── coverage.py          # Coverage data parser (coverage.json / .coverage)
│   └── analysis/
│       ├── __init__.py
│       ├── _shared.py       # Shared helpers (safe file reader, package derivation)
│       ├── effects.py       # 48-type SideEffectType taxonomy
│       ├── models.py        # Effect / FunctionRecord data models
│       ├── detector.py      # Python side-effect detector (analyze method)
│       └── complexity.py    # McCabe cyclomatic complexity (complexity method)
├── tests/
├── pyproject.toml
└── NOTICE
```

Delivered in issue #4: `detector.py`, `complexity.py`, `coverage.py`, `_shared.py`,
and the `analyze`, `complexity`, and `coverage` JSON-RPC methods.
Planned later: astroid-based name inference.

## License

Apache 2.0 -- see [LICENSE](LICENSE).
