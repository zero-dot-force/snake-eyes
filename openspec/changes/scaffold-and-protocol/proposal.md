## Why

snake-eyes is the Python Gaze external analyzer backend, but it has no Python source, no `pyproject.toml`, no tests, and no CI. Gaze (Go) spawns it as a subprocess and speaks JSON-RPC 2.0 over stdin/stdout (protocol v1.1.0), so the project cannot even boot without a scaffold and a working `initialize`/`shutdown` lifecycle. This change establishes that foundation.

## What Changes

- Add a Python package scaffold: `pyproject.toml`, `src/snake_eyes/__init__.py`, `src/snake_eyes/__main__.py`, and a `NOTICE` file for future gaze-py attribution.
- Add `src/snake_eyes/protocol.py` with stdlib `dataclasses` for the JSON-RPC 2.0 envelope and the `initialize`/`shutdown` method contracts, plus standard error codes.
- Add `src/snake_eyes/server.py`: a line-delimited JSON-RPC server loop over stdin/stdout with sequential dispatch and graceful error handling.
- Add `.github/workflows/ci.yml` running ruff, mypy, and pytest-with-coverage on Python 3.11 and 3.12.
- Add `tests/test_protocol.py`, `tests/test_server.py`, and `tests/test_cli.py` driving the server through stdin/stdout.

Out of scope (later issues): analysis, complexity, coverage, discovery, streaming, gaze-py source lift, `astroid`/`radon`/`coverage.py` runtime deps, and any change to the stale `specs/001-jsonrpc-prototype/` Speckit spec. A follow-up will retire or mark the stale spec as superseded; this change leaves it untouched.

## Capabilities

### New Capabilities
- `protocol`: JSON-RPC 2.0 envelope types and the `initialize`/`shutdown` method contracts (request params, result schemas, error codes, serialization).
- `server`: the line-delimited JSON-RPC stdio server loop — request parsing, sequential dispatch, and error handling.
- `cli`: package scaffold and the `snake-eyes --stdio` entry point (usage-on-error behavior).

### Modified Capabilities

None — this is the first implementation; no existing OpenSpec specs exist yet.

### Removed Capabilities

None.

## Impact

- New files under `src/snake_eyes/`, `tests/`, and `.github/workflows/`.
- No changes to existing code (there is none) and no runtime third-party dependencies — stdlib (`json`, `dataclasses`, `sys`) only.
- Dev-only dependencies added: `pytest`, `pytest-cov`, `mypy`, `ruff`.
- Establishes the project CI gate: ruff lint/format, mypy strict, pytest with 85% coverage fail-under.

## Constitution Alignment

- **I. Protocol Fidelity** — Implemented directly: exact v1.1.0 handshake (`protocol_version = "1.1.0"`), exact envelope/result field names, the standard JSON-RPC error taxonomy, and `data`-omission serialization, all pinned by tests.
- **II. Detection Accuracy** — N/A: no analysis/detection code is introduced in this change (scaffold + `initialize`/`shutdown` lifecycle only).
- **III. Python-Native Analysis** — N/A: no analysis/detection code is introduced in this change.
- **IV. Testability** — The coverage strategy is implemented now, not deferred: 100% unit targets for `protocol.py`, `server.py`, and `__main__.py`, and the 85% aggregate gate enforced in CI.
