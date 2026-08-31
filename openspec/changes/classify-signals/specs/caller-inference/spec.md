## ADDED Requirements

### Requirement: caller index public API
The system SHALL provide `src/snake_eyes/analysis/inference.py` exposing a caller-index API: `build_caller_index(root_path: str, patterns: list[str] | None) -> CallerIndex` and `CallerIndex.count(module: str, func_name: str) -> int`, where `module` is a dotted package path (e.g. `snake_eyes.analysis.detector`). `build_caller_index` SHALL enumerate the project's files exactly once via `_shared.ordered_file_list(root_path, patterns)` (which applies the `_shared` symlink-skip and excluded-directory guards) and SHALL then filter that enumerated list through `_shared.is_analyzable_file` to enforce the 16 MiB byte-cap and skip non-regular files BEFORE astroid parses any file, building a single astroid view over that bounded on-disk file set, so the whole-project call graph is constructed once per `extract_signals` invocation and never rebuilt per function. (The 16 MiB byte-cap and the regular-file check live in `_shared.is_analyzable_file`, not in `ordered_file_list`/`discover`, so the astroid caller-index path MUST apply that filter explicitly to honor the Constitution V resource bound.) `CallerIndex.count` SHALL be a pure lookup returning the number of inbound `Call` nodes across that file set whose inferred callee resolves to `func_name`; the callee SHALL be matched by its RESOLVED DEFINING FILE PATH against the analyzed file set (robust to `src/` and other project layouts) rather than by dotted-module-string equality. `build_caller_index` SHALL use an isolated per-request astroid manager (a fresh manager instance or `MANAGER.clear_cache()` at the start of each request, never the long-lived process-global `MANAGER` shared across requests) so counts cannot be contaminated by prior requests on other trees, and it SHALL restrict import resolution to the on-disk project rather than the ambient `sys.path` so counts are environment-independent. It SHALL operate on on-disk source only and SHALL NOT require the analyzed project to be installed or importable. The module SHALL also expose a thin, test-only convenience wrapper `count_callers(root_path: str, module: str, func_name: str, patterns: list[str] | None = None) -> int` that builds a one-off index and performs a single lookup; it is documented as rebuilding the index per call and SHALL NOT be used on the per-function adapter hot path.

#### Scenario: inbound calls are counted
- **WHEN** `count_callers` runs over a project where `func_name` in `module` is called from two other call sites
- **THEN** it returns `2`

#### Scenario: uncalled function returns zero
- **WHEN** `count_callers` runs for a function that no other code calls
- **THEN** it returns `0`

#### Scenario: per-request isolation across trees
- **WHEN** `count_callers` is invoked for one project tree and then for a different project tree within the same process/session
- **THEN** the second result is unaffected by the first, because each request uses an isolated per-request astroid manager that prevents cross-request cache contamination

#### Scenario: cross-module callers counted under a src/ layout
- **WHEN** a project uses a `src/` layout and module A calls a function defined in module B
- **THEN** the caller index returns a non-zero cross-module count by resolving the callee to its defining file path in module B, rather than comparing the root-relative dotted package (which would carry a spurious `src.` prefix and never match astroid's inferred module name)

### Requirement: astroid failures degrade to zero
`count_callers` SHALL NOT propagate astroid errors as RPC errors, across two distinct degradation modes. (a) **Whole-count failure**: if astroid raises any exception — including `AstroidError`/`InferenceError` subclasses plus `RecursionError`, `MemoryError`, and `OSError` — or cannot build a manager or module view, `count_callers` SHALL return `0` for the entire count rather than raising. (b) **Per-call omission**: if a single call site's callee resolves to `Uninferable`, `count_callers` SHALL omit that one call from the count and continue counting the rest. A caller count of `0` is a valid, well-formed result — never a protocol error.

#### Scenario: astroid raising yields zero, not an error
- **WHEN** astroid raises while inferring a module (simulated via monkeypatch)
- **THEN** `count_callers` returns `0` and no exception propagates to the caller

#### Scenario: Uninferable callee is not counted
- **WHEN** a call site's callee inference returns `Uninferable`
- **THEN** that call does not increment the count and no exception is raised

### Requirement: static analysis only, never executes analyzed code
`count_callers` SHALL perform static inference over source files only. It SHALL NOT import, execute, or otherwise run the analyzed project's code, consistent with Analysis Safety.

#### Scenario: analyzed project is not imported
- **WHEN** `count_callers` runs over a fixture module with an observable import-time side effect (e.g. writing a sentinel file or mutating a module-level global at import)
- **THEN** the side effect does not occur — an enforcing test asserts the sentinel is absent — because the source is inferred statically and never imported or executed
