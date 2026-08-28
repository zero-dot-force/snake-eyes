## 1. Effect taxonomy

- [x] 1.1 Create `src/snake_eyes/analysis/__init__.py` re-exporting `SideEffectType` and `TIER_MAP` (thin)
- [x] 1.2 Create `src/snake_eyes/analysis/effects.py` by lifting gaze-py's `effects.py` (38 `SideEffectType` members, `Tier` enum, `TIER_MAP`) with a provenance header crediting gaze-py / Matt Peter / Apache 2.0
- [x] 1.3 Add the 10 missing members (`ErrorSignal` P0; `GeneratorYield`, `ContainerMutation`, `StreamOutput` P1; `AsyncGeneratorYield`, `MetaprogrammingMutation`, `DescriptorEffect`, `ResourceManagement`, `ImportSideEffect`, `MonkeyPatch` P2) and their `TIER_MAP` entries

## 2. Data models

- [x] 2.1 Create `src/snake_eyes/analysis/models.py` with frozen `Effect` and `FunctionRecord` dataclasses (protocol-shaped, no gaze-py-only fields)
- [x] 2.2 Implement `function_record_to_dict` omitting `None` optionals (`location`, `target`, `detail`)

## 3. File discovery

- [x] 3.1 Create `src/snake_eyes/discovery.py` with frozen `DiscoveryResult` and `discover(root_path, patterns=None)`
- [x] 3.2 Implement `.py`-only discovery, POSIX-relative paths, `./...` pattern convention, directory exclusion list, and deterministic lexicographic sorting of both result lists
- [x] 3.3 Implement test classification (`test_` prefix, `_test.py` suffix, `tests`/`test` path component) with disjoint lists
- [x] 3.4 Implement symlink policy (skip directory and file symlinks) and `FileNotFoundError` on missing/non-directory root

## 4. Wire discover method

- [x] 4.1 Add a `discover` handler to `server.py` (`DEFAULT_DISPATCH`) that validates params and maps `FileNotFoundError` to `RpcError(INVALID_PARAMS)`
- [x] 4.2 Flip `capabilities.discover` to `true` in `protocol.py` `initialize_result` (leave other three flags `false`)

## 5. Tests

- [x] 5.1 Create `tests/test_effects.py` (48 members; every member in `TIER_MAP`; 10 new types' tiers; existing P0 set present)
- [x] 5.2 Create `tests/test_models.py` (`function_record_to_dict` omits None optionals; `type` canonical; frozen assignment raises)
- [x] 5.3 Create `tests/test_discovery.py` using `tmp_path` (src/tests split; `test_foo.py` root; `foo_test.py`; `.venv`/`__pycache__` excluded; sorted lexicographic output; empty project; missing root raises)
- [x] 5.4 Create `tests/test_discover_method.py` (JSON-RPC roundtrip against a temp project; `initialize` reports `"discover": true`)

## 6. Verification

- [x] 6.1 Run `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`
- [x] 6.2 Run `uv run mypy src/`
- [x] 6.3 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`
- [x] 6.4 Manually verify `uv run snake-eyes --stdio` answers `initialize` with `"discover": true` and a `discover` request against a temp project

<!-- spec-review: passed -->
<!-- code-review: passed -->
