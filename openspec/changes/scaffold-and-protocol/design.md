## Context

snake-eyes is the Python backend for Gaze's external analyzer protocol (JSON-RPC 2.0 over stdin/stdout, protocol v1.1.0). The project currently has no Python source, no packaging, no tests, and no CI — only a stale Speckit spec (`specs/001-jsonrpc-prototype/`) that predates protocol v1.1.0 and is explicitly superseded for handshake/lifecycle. This change lays the foundation: package scaffold, protocol types, a working stdio server loop, CI, and tests. Authoritative protocol source: unbound-force/gaze `docs/protocol.md` (v1.1.0) and `internal/protocol/types.go`. Build input: issue zero-dot-force/snake-eyes#2.

Constitution I (Protocol Fidelity) requires every JSON-RPC response to match the v1.1.0 schema exactly. Constitution IV (Testability) requires the coverage strategy to be implemented now, not deferred.

## Goals / Non-Goals

**Goals:**
- A minimal `snake-eyes` Python package (stdlib only at runtime) installable via `uv sync`.
- A JSON-RPC 2.0 stdio server implementing `initialize` and `shutdown` correctly per protocol v1.1.0.
- A CI pipeline (ruff, mypy, pytest with 85% coverage fail-under) on Python 3.11 and 3.12.
- Tests that drive the server through stdin/stdout and assert JSON field values.

**Non-Goals:**
- `analyze`, `complexity`, `coverage`, `discover`, `test_mapping`, `classify_signals`, or `analyze/stream` — these are later issues.
- Any gaze-py source lift (only a `NOTICE` placeholder is added).
- `astroid`, `radon`, `coverage.py` as dependencies.
- Logging library, config-file parsing, or modification of the stale Speckit spec.

## Decisions

1. **Transport is line-delimited JSON, not LSP Content-Length headers.**
   One JSON object per line over stdin/stdout. This matches Gaze protocol v1.1.0 and keeps the server trivially streamable. Alternative (LSP framing) rejected: the protocol spec mandates line-delimited JSON.

2. **Stdlib `dataclasses` for protocol types, serialized via `dataclasses.asdict` + `json.dumps`.**
   No pydantic. The envelope is small and fixed; a serialization dependency buys nothing at this scope and violates the "prefer stdlib" default. `asdict` with an explicit filter omits the optional error `data` key when `None` (the protocol forbids emitting `null` for omitted fields).

3. **Server reads `sys.stdin`/writes `sys.stdout` and accepts injected streams plus an injectable dispatch table.**
   A `Server` object takes `stdin`/`stdout`/`stderr` as constructor args so tests can inject `io.StringIO` and drive the loop deterministically. It also accepts an injectable dispatch table (method name → handler callable), defaulting to the built-in `initialize`/`shutdown` table, so a test can register a raising handler to exercise the `-32603` internal-error path through stdin/stdout. This satisfies the "drive through stdin/stdout, not private helpers" test mandate. The broken-pipe test injects a minimal stub whose `write` raises `BrokenPipeError` (not `io.StringIO`, which cannot raise).

4. **Sequential request processing.**
   Read a line, handle it, flush, repeat. No pipelining or concurrency — Gaze issues requests sequentially, and ordering matters for `shutdown`.

5. **Error taxonomy is the standard JSON-RPC 2.0 set.**
   `-32700` parse error (id `null`), `-32600` invalid request, `-32601` method not found, `-32602` invalid params (fired when `initialize` `params` is absent, non-object, or lacks a string `root_path`), `-32603` internal error. On handler exception, write `-32603` with the message and log tracebacks only to stderr (stdout is the protocol channel).

6. **`initialize` is idempotent; `shutdown` exits 0 after ack.**
   A second `initialize` returns a valid result. `shutdown` writes `{}` then the process exits 0. Empty lines are ignored; stdin EOF without `shutdown` exits 0 silently. Exit codes are surfaced as `SystemExit` raised in-process (the server loop raises `SystemExit(0)` after `shutdown`/EOF and `main()` propagates it); tests catch `SystemExit` from injected streams rather than spawning a subprocess.

7. **`--stdio` is the only CLI flag.**
   With `--stdio`, start the server and block. Without it, print `snake-eyes --stdio` to stderr and exit 2. No config files, no subcommands. `main(argv=None, *, stdin=None, stdout=None, stderr=None)` defaults each to `sys.*`, mirroring the `Server` seam so tests drive the entry point in-process.

8. **CI: `astral-sh/setup-uv` + `uv sync --locked`, matrix 3.11/3.12, four gates.**
   `ruff check`, `ruff format --check`, `mypy src/` (strict), and `pytest --cov=snake_eyes --cov-fail-under=85`. The 85% gate is a governance value and is not lowered. The `astral-sh/setup-uv` action SHALL be pinned to a full commit SHA (tag recorded as a trailing comment) for supply-chain integrity, and the workflow SHALL declare an explicit `permissions: contents: read` block (least privilege).

## Risks / Trade-offs

- [Protocol drift vs. Gaze v1.1.0] → Pin `protocol_version` to the literal `"1.1.0"` and assert it in tests; keep the envelope field names verbatim from the issue.
- [stdlib-only serialization omits `data` incorrectly] → Centralize in one `to_dict` helper with a `None`-omission rule and unit-test the exact JSON output.
- [stdout contamination from tracebacks] → Route all diagnostics to stderr; tests assert stdout contains only protocol JSON.
- [Coverage gate vs. small surface area] → `__main__.py`, `protocol.py`, and `server.py` each have explicit 100% unit targets so the aggregate 85% gate is comfortably met.
