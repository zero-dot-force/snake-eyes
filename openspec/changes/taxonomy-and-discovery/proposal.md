## Why

snake-eyes currently only has the JSON-RPC scaffold (`initialize`/`shutdown`) and no domain types. Every later analysis method — `analyze`, `complexity`, `coverage`, `test_mapping` — depends on the shared side-effect taxonomy, the protocol data models, and file discovery, none of which exist yet. Gaze's canonical taxonomy is 48 types, but the gaze-py reference implementation carries only 38; the analyzer would emit non-canonical or missing effect names without this change. The optional `discover` protocol method is also still `false` in `initialize`.

## What Changes

- Add `src/snake_eyes/analysis/effects.py`: lift gaze-py's 38-value `SideEffectType` `StrEnum`, `Tier` enum, and `TIER_MAP`, then add the 10 missing canonical types to reach the full 48, with a provenance header crediting gaze-py (Matt Peter, Apache 2.0).
- Add `src/snake_eyes/analysis/models.py`: protocol-shaped `Effect` and `FunctionRecord` frozen dataclasses plus a `function_record_to_dict` serialization helper.
- Add `src/snake_eyes/discovery.py`: `discover()` and `DiscoveryResult` for source/test file discovery with directory exclusion and test classification.
- Add `src/snake_eyes/analysis/__init__.py` (thin re-export of `SideEffectType` and `TIER_MAP`).
- Wire the `discover` JSON-RPC method onto the server and flip `capabilities.discover` to `true` in `initialize`; invalid/missing `root_path` maps to `-32602`.
- Add `tests/test_effects.py`, `tests/test_models.py`, `tests/test_discovery.py`, and `tests/test_discover_method.py`.

Out of scope (later issues): the `analyze`, `complexity`, `coverage`, `test_mapping`, and `classify_signals` methods; *detection* of any effect type (this change adds enum members and models only); gaze-py `models.py` fields that are not in the protocol payload.

## Capabilities

### New Capabilities
- `effects`: the 48-value `SideEffectType` `StrEnum`, the `Tier` enum, and the authoritative `TIER_MAP`.
- `models`: the `Effect` and `FunctionRecord` dataclasses and the `function_record_to_dict` serialization helper.
- `discovery`: the `discover()` function and `DiscoveryResult` (source/test file discovery rules).
- `discover-method`: the JSON-RPC `discover` method (params/result schema, error mapping) and the `initialize.capabilities.discover` flag.

### Modified Capabilities
None — `openspec/specs/` has no archived capabilities; the `scaffold-and-protocol` change (which first defined `initialize_result` and the server dispatch) is still unarchived. The `discover` capability flag flip and the new method are captured under the new `discover-method` capability above.

### Removed Capabilities
None.

## Impact

- New files: `src/snake_eyes/analysis/__init__.py`, `src/snake_eyes/analysis/effects.py`, `src/snake_eyes/analysis/models.py`, `src/snake_eyes/discovery.py`, and four test modules.
- Modified files: `src/snake_eyes/protocol.py` (flip `discover` to `true` in `initialize_result`), `src/snake_eyes/server.py` (add `discover` handler to `DEFAULT_DISPATCH`).
- No new runtime dependencies — stdlib only (`enum`, `dataclasses`, `os`, `fnmatch`, `pathlib`). The existing `NOTICE` already attributes gaze-py; the lifted file carries its own provenance header.
- The 10 new enum members carry no detection behavior; nothing in the existing scaffold changes semantics except the one capability flag.

## Constitution Alignment

- **I. Protocol Fidelity** — Emits only canonical Gaze type strings (`"ReturnValue"`, not aliases); `Effect`/`FunctionRecord` match the v1.1.0 `analyze` payload keys; `discover` params/result and `-32602` mapping follow the protocol; `initialize` flips exactly one flag.
- **II. Detection Accuracy** — Enum members only; no detection, so no false positives/negatives are introduced. Ambiguity is avoided by adding the full 48-type vocabulary now.
- **III. Python-Native Analysis** — Uses `enum.StrEnum`, `dataclasses`, and `os.walk` (stdlib); no reimplementation of Python semantics.
- **IV. Testability** — Coverage strategy is specified now (`effects.py` 100%, `models.py` 100%, `discovery.py` 95%+; the new `discover` handler in `server.py` and the `initialize_result` flag flip are exercised by the JSON-RPC roundtrip test in task 5.4, all under the unchanged 85% aggregate gate).
- **V. Analysis Safety** — Static analysis only; discovery walks the filesystem and never executes analyzed code.
