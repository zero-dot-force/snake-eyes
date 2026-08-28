## Context

Gaze protocol v1.1.0 defines 48 canonical side-effect types (`internal/taxonomy/types.go`). The gaze-py reference implementation (Matt Peter, Apache 2.0) carries 38 of those 48 in `src/gaze_py/taxonomy/effects.py`. snake-eyes has permission to lift gaze-py code, and its `NOTICE` already attributes gaze-py. The scaffold change (unarchived) gives us `protocol.py` (`initialize_result`, `to_dict`, error codes) and `server.py` (`Server`, `DEFAULT_DISPATCH`, `RpcError`).

This change adds the shared domain types every later analysis method needs, plus the optional `discover` method. No detection code is written — the 10 new enum members are vocabulary only.

## Goals / Non-Goals

**Goals:**
- Land the exact 48-type `SideEffectType` taxonomy with `TIER_MAP`, matching Gaze's canonical strings and tiers.
- Land protocol-shaped `Effect` and `FunctionRecord` dataclasses whose JSON keys match the v1.1.0 `analyze` payload.
- Land `discover()` for source/test file discovery with deterministic exclusion and classification rules.
- Wire the `discover` JSON-RPC method and flip `capabilities.discover` to `true`.

**Non-Goals:**
- `analyze`, `complexity`, `coverage`, `test_mapping`, `classify_signals` implementations.
- Detection logic for any effect type (enum members and models only).
- gaze-py's internal `models.py` fields (`visibility`, `is_test`, `is_generator`, `complexity`, `id`, `Signal`, `Score`, `Summary`, quality types) — these are not part of the protocol payload.
- Go's full `./pkg/...` package-prefix semantics in `patterns`.

## Decisions

**D1 — Use `enum.StrEnum` for `SideEffectType`.**
Python 3.11+ `StrEnum` members are `str` subclasses, so `json.dumps` serializes them as bare strings without a custom encoder. This matches gaze-py's existing choice and satisfies "emit canonical names only". Alternative: `enum.Enum` with explicit `.value` coercion — rejected as needless friction.

**D2 — Lift gaze-py `effects.py`, then add 10 members.**
Keep the 38 existing member names and `TIER_MAP` entries verbatim; append the 10 missing members with the exact names/tiers from the issue (`ErrorSignal` P0; `GeneratorYield`, `ContainerMutation`, `StreamOutput` P1; `AsyncGeneratorYield`, `MetaprogrammingMutation`, `DescriptorEffect`, `ResourceManagement`, `ImportSideEffect`, `MonkeyPatch` P2). `TIER_MAP` is a gatekeeping value: existing tier assignments are not reclassified, and no local aliases (e.g. `ArgumentMutation`) are added as members — snake-eyes emits canonical names only. gaze-py's source files carry no per-file copyright header, so we add a provenance header to the lifted file crediting gaze-py / Matt Peter / Apache 2.0 (satisfying the "preserve copyright header" requirement; the `NOTICE` covers repository-level attribution).

**D3 — Reshape `Effect` to the protocol payload, not gaze-py's `SideEffect`.**
gaze-py's `SideEffect` has `id`, `tier`, and `target` (qualified function name). The protocol wants `type` (canonical string), `description`, and optional `location`/`target`/`detail`. `Effect.type` is a `str` (not the enum) because the wire format is the canonical string; the detector (later) converts `SideEffectType` → `str` via the `StrEnum` value. `detail` is opaque `dict | None`.

**D4 — Omit `None` optionals from JSON.**
`function_record_to_dict` drops `location`, `target`, and `detail` when `None` (and drops `side_effects` when empty is not needed since it defaults to `()` and always serializes as a list). Rationale: Gaze's optional fields stay optional; the protocol forbids emitting `null` for omitted fields (same rule already applied to error `data` in `protocol.py`). This keeps the analyzer's own `to_dict` independent of the RPC-envelope `to_dict`.

**D5 — Discovery via `os.walk` with a fixed exclusion set and no symlink following.**
Walk with `followlinks=False` so directory symlinks are never descended (cycle safety); file symlinks are skipped entirely (simplest deterministic behavior). Only `.py` files are returned (`.pyi` stubs excluded). Paths are POSIX-relative to `root_path`. Test classification: filename starts with `test_`, ends with `_test.py`, or any path component is `tests`/`test`. A file matching test rules goes to `test_files` only. `patterns` follows Gaze's `["./..."]` convention: `None`/`[]`/`["..."]`/`["./..."]` → whole tree; a relative directory pattern walks that subtree; a glob (`**/*.py`) is resolved relative to root; Go's `./pkg/...` package semantics are reduced to "directory prefix + recursive".

**D6 — `discover` handler maps `FileNotFoundError` to `-32602`.**
The `Server` already catches `RpcError` and routes to the matching JSON-RPC error. The `discover` handler validates params, calls `discover()`, catches `FileNotFoundError`, and raises `RpcError(INVALID_PARAMS, ...)`. The handler returns a plain dict `{"source_files": [...], "test_files": [...]}` (lists, not tuples), so `JsonRpcSuccess` serializes directly. `initialize_result` flips only `capabilities.discover` to `true`; the other three flags stay `false`.

## Risks / Trade-offs

- [Drift if Gaze adds a 49th type] → `TIER_MAP` is the single authoritative mapping and is tested to be complete (`len == 48` and every member has an entry); a future taxonomy bump is a one-file change.
- [Wrong tier for the 10 new types] → pinned by a table-driven test asserting each new type's exact tier.
- [Symlink/cycle edge cases in discovery] → deterministic "skip all symlinks" rule eliminates the class of bug; documented in spec.
- [Tuple vs list on the wire] → `discover` handler and `discovery.discover()` return tuples internally, but the RPC handler converts to lists so JSON is always arrays.
- [Copyright provenance] → gaze-py has no per-file headers; we add an explicit provenance header and rely on the existing `NOTICE`. If a future gaze-py release adds headers, re-lift and preserve them verbatim.

## Migration Plan

No runtime migration — this is additive. The only behavior change to existing code is `initialize` now reporting `"discover": true` (from `false`), which is forward-compatible with Gaze (an optional capability going from off to on). No rollback path beyond reverting the commit.

## Open Questions

None. Every previously-open decision (tier assignments, discovery exclusion set, symlink policy, `detail`/`target`/`location` omission) is resolved in the issue and codified in Decisions D1–D6.
