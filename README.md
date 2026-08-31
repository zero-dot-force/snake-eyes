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
| `classify_signals` | Implemented |

Capability flags advertised at handshake: `discover` and
`classify_signals` are `true`; `test_mapping` and `streaming` are `false`.
Side-effect detection and classification-signal extraction are
implemented. coverage.py (`>=7.0,<8`) and astroid (`>=3.0,<4`,
caller-count inference) are runtime dependencies (shipped). `radon` is
not used — cyclomatic complexity is computed via a lifted McCabe
implementation (no radon dependency).

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

```text
snake-eyes/
├── src/snake_eyes/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (snake-eyes --stdio)
│   ├── server.py            # JSON-RPC server (stdin/stdout)
│   ├── protocol.py          # Request/response types
│   ├── discovery.py         # File discovery (os.walk)
│   ├── coverage.py          # Coverage data parser (coverage.json / .coverage)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── _shared.py       # Shared helpers (safe file reader, package derivation)
│   │   ├── effects.py       # 48-type SideEffectType taxonomy
│   │   ├── models.py        # Effect / FunctionRecord data models
│   │   ├── detector.py      # Python side-effect detector (analyze method)
│   │   ├── complexity.py    # McCabe cyclomatic complexity (complexity method)
│   │   └── inference.py     # astroid caller-count inference (classify_signals)
│   └── signals/
│       ├── __init__.py
│       ├── interface.py     # interface source extractor (lifted from gaze-py)
│       ├── visibility.py    # visibility source extractor (lifted from gaze-py)
│       ├── caller.py        # caller_count source extractor (lifted from gaze-py)
│       ├── naming.py        # naming_convention extractor (lifted from gaze-py)
│       ├── docstring.py     # docstring source extractor (lifted from gaze-py)
│       ├── _routing.py      # effect-type → category routing (naming/docstring)
│       ├── _types.py        # SignalResult value type
│       └── adapter.py       # extract_signals fan-out (classify_signals method)
├── tests/
├── pyproject.toml
└── NOTICE
```

Delivered in issue #4: `detector.py`, `complexity.py`, `coverage.py`, `_shared.py`,
and the `analyze`, `complexity`, and `coverage` JSON-RPC methods.
Delivered in issue #5: the `signals/` extractors, `analysis/inference.py`
(astroid caller-count inference), and the `classify_signals` JSON-RPC method.

## Limits & Troubleshooting

Snake Eyes performs static analysis only on untrusted source and enforces
fixed resource bounds (not configurable in v1):

- **File size cap** — files larger than 16 MiB (`MAX_FILE_BYTES`) are skipped
  before they are opened.
- **AST depth budget** — traversal is bounded at `MAX_AST_DEPTH` (200) nested
  nodes to prevent stack exhaustion.

When a file is skipped — because it is non-regular (FIFO/device/socket),
oversized, unparseable (syntax error), or exceeds the depth budget — Snake Eyes
emits a one-line diagnostic to **stderr** and continues. A single bad file never
aborts the request, and **stdout carries only the JSON-RPC response**. If Gaze
reports fewer functions than expected, check Snake Eyes' stderr for `skipping`
diagnostics.

Coverage data is optional: when `coverage.json` / `.coverage` is absent or
invalid, the `coverage` method returns an empty result (`[]`), never an error.

## License

Apache 2.0 -- see [LICENSE](LICENSE). Portions of `detector.py`,
`complexity.py`, and the `signals/` extractors (`interface.py`, `visibility.py`,
`caller.py`, `naming.py`, `docstring.py`, `_routing.py`) are lifted or
reconstructed from gaze-py under Apache-2.0; see [NOTICE](NOTICE) for
attribution.
