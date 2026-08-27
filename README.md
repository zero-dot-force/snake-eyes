# Snake Eyes

**Python analyzer backend for [Gaze](https://github.com/unbound-force/gaze).**

Snake Eyes is a Gaze-spawned subprocess. It speaks JSON-RPC 2.0 over stdin/stdout
(protocol v1.1.0). Gaze owns the CLI, scoring, and reports.

## Current status (v0.1.0)

This release is the project scaffold and protocol lifecycle only:

| Method | Status |
|--------|--------|
| `initialize` | Implemented |
| `shutdown` | Implemented |
| `discover`, `analyze`, `complexity`, `coverage` | Not implemented (`-32601`) |

Capability flags advertised at handshake (`discover`, `test_mapping`,
`classify_signals`, `streaming`) are all `false`. Side-effect detection and
analysis dependencies (`astroid`, `radon`, `coverage.py`) are later issues.

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
│   └── protocol.py          # Request/response types
├── tests/
├── pyproject.toml
└── NOTICE
```

Planned later: file discovery, analysis, complexity, and coverage (issues #3–#6).

## License

Apache 2.0 -- see [LICENSE](LICENSE).
