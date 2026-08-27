## 1. Package scaffold

- [x] 1.1 Create `pyproject.toml` (name `snake-eyes`, dynamic version `0.1.0` single-sourced from `__init__.py` via `[tool.hatch.version]`, `requires-python >=3.11`, Apache-2.0, `src/` layout, dev deps `pytest`/`pytest-cov`/`mypy`/`ruff` under `[dependency-groups] dev`, `snake-eyes = "snake_eyes.__main__:main"` entry, ruff line-length 88, mypy strict, testpaths `tests`, cov fail-under 85 with branch coverage) and commit the generated `uv.lock` for reproducible CI
- [x] 1.2 Create `src/snake_eyes/__init__.py` with `__version__ = "0.1.0"`
- [x] 1.3 Create `NOTICE` with the exact attribution content specified in `specs/cli/spec.md`

## 2. Protocol types

- [x] 2.1 Create `src/snake_eyes/protocol.py` with `JsonRpcRequest`, `JsonRpcSuccess`, `JsonRpcErrorBody`, `JsonRpcError` dataclasses
- [x] 2.2 Add standard error code constants (`PARSE_ERROR`, `INVALID_REQUEST`, `METHOD_NOT_FOUND`, `INVALID_PARAMS`, `INTERNAL_ERROR`)
- [x] 2.3 Implement `initialize` request/result construction (`analyzer_name`, `language`, `language_version` from `sys.version_info`, `protocol_version = "1.1.0"`, four `false` capability flags)
- [x] 2.4 Implement `shutdown` result (`{}`)
- [x] 2.5 Implement serialization via a recursive `to_dict` helper + `json.dumps` with the `data`-omitted-when-`None` rule

## 3. Server loop

- [x] 3.1 Create `src/snake_eyes/server.py` with a `Server` class accepting injected `stdin`/`stdout`/`stderr` and an injectable dispatch table (method name → handler), defaulting to `initialize`/`shutdown`
- [x] 3.2 Implement line-delimited read/write with flush after every response
- [x] 3.3 Implement sequential dispatch table (`initialize`, `shutdown`) and `-32601` fallback
- [x] 3.4 Implement error handling: `-32700` parse error (id null), `-32600` invalid request, `-32603` internal error (tracebacks to stderr only)
- [x] 3.5 Implement idempotent `initialize` and `shutdown` exit-0-after-ack; empty-line ignore and EOF-exit-0

## 4. CLI entry point

- [x] 4.1 Create `src/snake_eyes/__main__.py` with `main()` parsing `--stdio`
- [x] 4.2 `--stdio` present → start server and block; absent → usage to stderr and exit 2

## 5. Tests

- [x] 5.1 Create `tests/test_protocol.py` covering envelope serialization, falsy/string `id` round-trip, error codes, initialize request/result schema, shutdown result, and `data`-omission
- [x] 5.2 Create `tests/test_server.py` covering all `specs/server/spec.md` scenarios (initialize roundtrip, unknown method, malformed JSON, missing method, missing `jsonrpc`, wrong `jsonrpc` version, non-object request, empty-line ignore, CRLF line endings, order preservation, repeated initialize, invalid-params `-32602`, reserved methods → `-32601`, shutdown, EOF, broken-pipe clean teardown, `-32603` internal error via an injected raising handler) driving through injected stdin/stdout
- [x] 5.3 Create `tests/test_cli.py` covering `__main__.main()` for `--stdio` present (starts server) and absent (usage + exit 2), `__version__`, package metadata, and `NOTICE` exact-text content

## 6. CI

- [x] 6.1 Create `.github/workflows/ci.yml` (push+PR to main, ubuntu-latest, Python 3.11/3.12 matrix, `astral-sh/setup-uv` pinned to a full commit SHA resolved from the upstream repo at authoring time, `uv sync --locked`, explicit `permissions: contents: read` block, and a header comment block describing the workflow's purpose)
- [x] 6.2 Add the four gate steps: `ruff check`, `ruff format --check`, `mypy src/`, `pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`

## 7. Verification

- [x] 7.1 Run `uv sync --locked` from a clean checkout and confirm it succeeds
- [x] 7.2 Run `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`
- [x] 7.3 Run `uv run mypy src/`
- [x] 7.4 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`
- [x] 7.5 Manually verify `uv run snake-eyes --stdio` waits on stdin and the initialize→shutdown lifecycle works

<!-- spec-review: passed -->
<!-- code-review: passed -->
