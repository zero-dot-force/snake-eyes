## Context

Gaze's universal scoring engine classifies each side effect as contractual, incidental, or ambiguous. The Go core owns that formula (org constitution CC-001–CC-006): it sums five weighted signals, applies a tier boost, and applies a contradiction penalty. It does **not** know how to extract those signals from Python — that is the analyzer's job. gaze-py solves the same problem for a pure-Python toolchain, but it does two things: it *extracts* five mechanical signals (`src/gaze_py/classify/signals/*.py`) and then *scores* them locally (`src/gaze_py/classify/engine.py`).

snake-eyes already ships the pieces this change builds on, delivered by #4 (analysis-methods, merged): the `analyze_path`/`analyze_source` detector, the 48-value `SideEffectType` taxonomy (`analysis/effects.py`), the `Effect`/`FunctionRecord` models, and the shared discovery/AST layer (`_shared.py`, `discovery.py`). The one advertised-but-unimplemented optional capability that remains is `classify_signals` (`capabilities.classify_signals: false`, method returns `-32601`).

The constraint that shapes this whole design: **Gaze owns scoring, snake-eyes owns signal extraction.** If snake-eyes also scored, two implementations of the formula would drift. So snake-eyes reconstructs the gaze-py *extractors* (from their documented behavior) and never the *engine*.

## Goals / Non-Goals

**Goals:**
- Implement the `classify_signals` JSON-RPC method returning `{"signals": [...]}` with the exact protocol v1.1.0 field names (`function`, `package`, `side_effect_type`, `source`, `weight`, and `reasoning`). `reasoning` is a protocol-optional field that snake-eyes always emits as a short, non-empty string.
- Emit only the five mechanical signals from exactly five sources: `interface`, `visibility`, `caller_count`, `naming_convention`, `docstring`.
- Faithfully reproduce gaze-py's documented extraction logic (and its weights) so Gaze's formula receives the same signals it would for equivalent Python code.
- Degrade gracefully: an astroid inference failure yields `caller_count = 0`, never an RPC error.
- Flip `capabilities.classify_signals` to `true` to match the implemented behavior.

**Non-Goals:**
- No scoring: no 5-signal sum, no tier boost, no contradiction penalty, no `contractual`/`incidental`/`ambiguous` label. gaze-py `classify/engine.py` is NOT lifted.
- No sixth signal source and no `type_annotation` extractor.
- No retuning of gaze-py signal weights (they are gate values, not tunables).
- No `test_mapping`, no `analyze/stream` streaming, no `classification` field on `analyze` results.
- No importing or executing the analyzed project.

## Decisions

### Decision: Reconstruct the five extractors, never the engine
snake-eyes reconstructs `interface.py`, `visibility.py`, `caller.py`, `naming.py`, `docstring.py` from gaze-py's documented behavior into a new `src/snake_eyes/signals/` package and writes an original orchestrator (`adapter.py`) in place of gaze-py's `engine.py`.

*Rationale:* The classification formula lives in the Gaze Go core. Lifting the engine would create a second scorer that could drift from the canonical one — a Protocol Fidelity (Principle I) violation waiting to happen. Extractors are the mechanical, language-specific part that legitimately belongs in the analyzer.

*Alternatives considered:* (a) Reimplement extractors from scratch — rejected: duplicates well-tested gaze-py logic and invites weight drift. (b) Lift the engine and emit labels — rejected: violates the Gaze-owns-scoring boundary and the issue's explicit decision.

### Decision: Emit raw signals only; no labels, no arithmetic
`adapter.py` returns a flat list of signal dicts. It does not sum weights, clamp them, dedupe across extractors, or assign a label. Multiple signals for the same function-effect pair (e.g. one `naming_convention` and one `docstring`) are expected and all are emitted.

*Rationale:* Gaze consumes the raw signals and runs the formula itself. Any aggregation here would pre-empt (and potentially contradict) the Go core.

### Decision: Preserve gaze-py weights verbatim
Each extractor's weight values match gaze-py's documented values exactly (e.g. the `interface` extractor yields weight `30` for an ABC/`typing.Protocol` base). Where `caller.py` buckets inbound-call counts, the bucket boundaries and their weights are preserved as-is.

*Rationale:* The weights are inputs to a governance gate (Gaze's classification thresholds). Per the Gatekeeping Value Protection rule, an agent MUST NOT change gate values to make a local test pass — and there is no local scorer to satisfy anyway. Tests assert the gaze-py weights; they never redefine them.

### Decision: Map the 10 new Python effect types to their closest gaze-py branch
gaze-py's extractors predate the 10 Python-specific `SideEffectType` values added beyond gaze-py's original 38 (and also lack a branch for the gaze-py-original `ClosureCaptureMutation`). Where an extractor switches on effect type (`naming.py`, `docstring.py`), each such type is routed to the closest existing branch:

| New type | Behaves like | Reason |
|---|---|---|
| `GeneratorYield`, `StreamOutput`, `AsyncGeneratorYield` | `ReturnValue` | value/output-producing |
| `MonkeyPatch` | `ReflectionMutation` | dynamic attribute mutation |
| `ContainerMutation` | `SliceMutation`/`MapMutation` (P1 mutation) | container/collection mutation |
| `DescriptorEffect`, `ResourceManagement`, `MetaprogrammingMutation`, `ImportSideEffect` | closest P2/mutation branch | state-mutating effects |
| `ClosureCaptureMutation` (gaze-py-original, P4 exotic) | `ReflectionMutation` (P4 exotic) | closure-capture mutation |
| `ErrorSignal` | error/raise branch (like `ErrorReturn`) | error semantics |

An effect type that matches no keyword or prefix SHALL return `None` (no signal) — the extractor MUST NOT raise `KeyError` on an unrecognized type. This satisfies Detection Accuracy (Principle II): ambiguity over omission, but never a crash.

### Decision: Use astroid for caller counting, over on-disk files only
`analysis/inference.py` exposes `build_caller_index(root_path, patterns) -> CallerIndex`, which enumerates files exactly once via `_shared.ordered_file_list(root_path, patterns)` (which applies the `_shared` symlink-skip and excluded-directory guards) and then filters that enumerated list through `_shared.is_analyzable_file` to enforce the 16 MiB byte-cap and skip non-regular files **before** astroid parses any file — the byte-cap and regular-file check live in `is_analyzable_file`, not in `ordered_file_list`/`discover`, so the astroid path MUST apply that filter explicitly to honor the Constitution V resource bound. It builds a single astroid view over that bounded on-disk file set — **once per `extract_signals` invocation**, never rebuilt per function. `CallerIndex.count(module, func_name) -> int` is a pure lookup that counts `Call` nodes whose inferred callee resolves to `func_name`; the callee is matched by its **resolved defining file path** against the analyzed file set (robust to `src/` layouts), not by dotted-module-string equality (which would mismatch `derive_package`'s root-relative `src.pkg.mod` against astroid's inferred `pkg.mod`). The build isolates per-request astroid state by calling `astroid.MANAGER.clear_cache()` at the start of each request (and again in a `finally` after the build, to bound resident memory), so no parsed state is carried across requests. Rather than mutating `sys.path`, the build **short-circuits inference**: it first collects the set of function names defined anywhere in the analyzed file set and only attempts astroid inference for a call site whose unqualified name is in that set. Calls into stdlib/third-party APIs are therefore never inferred, so ambient `site-packages` are not parsed in the common case (a callee that merely shares an unqualified name with an in-project function may still be inferred, and such transitive parsing is not bounded by the 16 MiB cap — a `MemoryError` there degrades the whole index to empty). Counts are further scoped by matching each resolved callee's **defining file path** against the analyzed set, so a count only ever reflects in-project callers. A thin, test-only `count_callers(root_path, module, func_name, patterns=None) -> int` wrapper builds a one-off index and does a single lookup; it is documented as rebuilding per call and is never on the per-function adapter hot path.

*Rationale:* Counting inbound callers requires cross-module name resolution, which the stdlib `ast` cannot do. astroid is the pylint-maintained, Python-native inference engine — the right Principle III (Python-Native Analysis) tool.

*Alternatives considered:* (a) `ast`-only textual matching of call names — rejected: cannot distinguish `foo()` in different modules, produces false counts. (b) Import the project and use `inspect`/runtime graph — rejected: violates Analysis Safety (Principle V); analyzed code is untrusted and must never be executed.

### Decision: astroid failures degrade to `caller_count = 0`
While building the index or parsing a file, a degrade-class exception (`AstroidError`/`InferenceError` subclasses, plus `RecursionError`, `MemoryError`, and `OSError`), or an inability to build a manager or module view, yields `0` for the affected counts — degrading the whole index to empty in the outer case, or skipping the offending file in the per-file case. At an individual call site, **any** inference exception — including ones outside that tuple, since astroid inference can raise `AttributeError`/`TypeError`/`KeyError`/`RuntimeError` on pathological input — or an `Uninferable` callee causes that one call to be omitted while counting continues. Each degrade path emits a one-line diagnostic to stderr. A `0` count means the `caller` extractor emits whatever its zero-bucket signal is (possibly `None`) — but never an RPC error.

*Rationale:* astroid inference is best-effort on untrusted, possibly-partial source. A failure to infer is a missing signal, not a protocol failure. This keeps the method robust (Principle V) and the response well-formed (Principle I).

### Decision: Adapter algorithm
`extract_signals(root_path, patterns)`:
1. `records = analyze_path(root_path, patterns)` (reuses the #4 detector; inherits its discovery, ordering, parse-error skipping, and resource bounds).
2. Re-parse each file's AST for class bases, function name, docstring, and `__all__` membership (which `FunctionRecord` does not carry): enumerate via `_shared.ordered_file_list(root_path, patterns)` and read through `_shared.iter_source_files`, mapping each `FunctionRecord` to its enclosing class by locating the `def` at `FunctionRecord.line` and taking its enclosing `ClassDef`. Build the caller index with a single `build_caller_index(root_path, patterns)` call. Both the AST re-parse and `build_caller_index` receive the **same** `(root_path, patterns)`, so every consumer enumerates the identical deterministic, pattern-consistent file set (this is the known, accepted trade-off that `analyze_path`, the adapter re-parse, and `build_caller_index` each walk that same file set). Then, for each `FunctionRecord` and each `Effect` on it, run all five extractors with those AST inputs, the effect's `SideEffectType`, and the function's caller count via `CallerIndex.count`.
3. For every non-`None` extractor result, append one signal dict `{function, package, side_effect_type, source, weight, reasoning}` using the effect's type as `side_effect_type`.
4. A function with zero effects contributes zero signals.
5. No de-duplication across extractors; no weight arithmetic; no label.

*Rationale:* This is the thin, deterministic glue that maps snake-eyes' detector output to the five-signal protocol shape without re-implementing the engine.

### Decision: Server wiring mirrors the existing analysis handlers
A new `_classify_signals` handler validates params via the existing `_validate_analysis_params` (missing/invalid `root_path` → `-32602`, non-list `patterns` → `-32602`), calls `signals.adapter.extract_signals`, catches `FileNotFoundError` → `-32602`, and returns `{"signals": [...]}`. It is registered in `DEFAULT_DISPATCH` under the key `classify_signals`. `protocol.initialize_result()` flips `classify_signals` to `true`.

*Rationale:* Consistency with the #4 handlers (`_analyze`, `_complexity`, `_coverage`) keeps the protocol surface uniform and reuses proven validation.

## Risks / Trade-offs

- **astroid inference is imperfect on partial or dynamic code** → caller counts may undercount; mitigated by degrading to `0` and treating caller as one of five signals (Gaze's formula tolerates a missing signal). Documented as expected behavior, not a bug.
- **astroid is a heavier dependency than `ast`** (parses and infers) → pinned `>=3.0,<4` with a single-major ceiling (matching the `coverage>=7.0,<8` precedent); used only in `inference.py`; the rest of the analyzer stays on stdlib `ast`. No known applicable CVE at this range at time of writing (SC-005).
- **gaze-py extractors may not cover the 10 new effect types** → explicit closest-branch mapping table above; unmatched types return `None`, never raise. Covered by unit tests per extractor.
- **Weight drift risk if a test "fixes" a weight** → tests assert gaze-py weights as constants; the Gatekeeping Value Protection rule forbids editing them to pass. If a lifted weight ever seems wrong, stop and escalate rather than edit.
- **Accidental label leakage** → a negative test scans `src/snake_eyes/signals/` via `tokenize`/AST (not a raw grep) for `contractual`/`incidental`/`ambiguous` as assigned outputs; the words may appear only in comments that forbid them.

## Migration Plan

Additive change; no migration or rollback of persisted data.
1. Add `astroid>=3.0,<4` to `pyproject.toml`; refresh `uv.lock` via `uv lock`.
2. Land `signals/` extractors + `inference.py` + `adapter.py` with tests (green under the 85% project gate; per-file targets in the spec).
3. Wire `_classify_signals` into `DEFAULT_DISPATCH` and flip the capability flag; add the JSON-RPC e2e test.
4. Update `README.md`/`AGENTS.md` status notes.

Rollback: revert the change; `classify_signals` returns to `-32601` and the capability flag returns to `false`. No client that only used required methods is affected.

Per the constitution, spec artifacts MUST be committed before implementation, and implementation commits MUST NOT be combined with spec commits.

## Open Questions

None. Issue #5 states "Do not ask clarifying questions. Every decision is already made below," and its defaults resolve every choice: emit raw signals only; reconstruct extractors not the engine; match protocol v1.1.0 field names exactly. Exact non-`interface` weight values and `caller` bucket boundaries are the values gaze-py defines, reconstructed from its documented behavior and preserved as gate values (not invented to satisfy a local test).
