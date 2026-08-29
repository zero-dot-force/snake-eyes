## ADDED Requirements

### Requirement: cyclomatic complexity computation
The system SHALL provide a `compute_complexity(root_path, patterns)` public entry point that returns per-function McCabe complexity entries. The per-function McCabe logic is implemented as the private `_cyclomatic_complexity` helper, lifted from gaze-py, which counts the standard McCabe decision points (branch and boolean-operator nodes) and is deterministic for identical input.

#### Scenario: linear function has complexity 1
- **WHEN** complexity is computed for `def f():\n    return 1\n`
- **THEN** the complexity is `1`

#### Scenario: branching increments complexity
- **WHEN** complexity is computed for a function containing an `if`/`elif`/`else` chain combined with a boolean `and`
- **THEN** the complexity equals the exact McCabe integer for that structure, documented in the fixture as a hand-derived arithmetic comment (e.g. `# base 1 + if + elif + and = 4`); the expected value MUST NOT be obtained by running the implementation

### Requirement: per-function complexity over discovered files
The system SHALL compute complexity for every `def` and `async def` across the ordered concatenation of the sorted `source_files` then `test_files` returned by `discovery.discover()`, de-duplicated preserving first occurrence. Nested functions and methods of nested classes SHALL each receive their own complexity entry. Lambdas SHALL NOT be treated as functions.

#### Scenario: nested function gets its own complexity entry
- **WHEN** complexity runs over a module defining `def outer():` containing `def inner():`
- **THEN** both `outer` and `inner` receive separate complexity entries

#### Scenario: lambda excluded from complexity
- **WHEN** complexity runs over a module containing `f = lambda x: x`
- **THEN** no complexity entry is produced for the lambda

### Requirement: complexity entry fields
Each complexity entry SHALL carry `name` (unqualified definition name), `package` (dotted module path derived from the file path relative to `root_path`), `file` (path relative to `root_path`), `line` (definition line), and `complexity` (integer). Duplicate nested names SHALL each appear as a separate entry distinguished by `line`. The `package` field MUST be derived using the shared `derive_package` helper: strip `.py`, replace `/` with `.`, and drop a trailing `.__init__` (so `pkg/__init__.py` → `pkg`). This helper is shared by the detector and complexity modules only — coverage result rows carry `file` + `function` (no `package`) per the protocol schema, so coverage does NOT use `derive_package`. MUST NOT be reimplemented inline.

#### Scenario: entry carries required fields
- **WHEN** complexity is computed for a function `f` in `pkg/mod.py`
- **THEN** the entry has `name == "f"`, `package == "pkg.mod"`, `file == "pkg/mod.py"`, an integer `line`, and an integer `complexity`

#### Scenario: package drops trailing __init__
- **WHEN** complexity is computed for a function in `pkg/__init__.py`
- **THEN** the entry `package` is `pkg`

### Requirement: gaze-py provenance retained
The lifted `complexity.py` SHALL retain the gaze-py copyright header (Matt Peter, Apache 2.0). No `radon` dependency SHALL be introduced for complexity computation. In addition, `complexity.py` MUST add an Apache-2.0 §4(b) change notice immediately following the original copyright header, e.g.:

```
# Modified 2026 by zero-dot-force: adapted for mypy --strict and ruff.
```

#### Scenario: provenance header present
- **WHEN** `src/snake_eyes/analysis/complexity.py` is inspected
- **THEN** it contains the gaze-py Apache 2.0 provenance header and an Apache-2.0 §4(b) change notice attributing zero-dot-force

### Requirement: complexity skips parse-error and over-bound files
The complexity computation SHALL skip any file that raises `(SyntaxError, ValueError, RecursionError, OSError, MemoryError)` during parsing and continue processing the remaining files in the request. A per-file diagnostic MUST be emitted to stderr; it MUST NOT appear in the stdout JSON-RPC result and the result MUST NOT include an `errors` array.

To protect against untrusted analyzed source, a per-file byte-size cap of `MAX_FILE_BYTES = 16 MiB` (fixed constant, not user-configurable in v1) enforced via `stat` before `open()` (regular-file-only; any candidate that is not `S_ISREG` MUST be skipped with a stderr diagnostic) and a fixed AST-depth/recursion budget MUST bound analysis. A file that exceeds either bound MUST be skipped-and-continued (exactly as a parse error is), never aborting the whole request. The per-file diagnostic for an over-bound file MUST go to stderr only.

#### Scenario: syntax-error file does not abort the batch
- **WHEN** complexity is requested for a tree containing `syntax_error.py` (unparseable) alongside one or more valid Python files
- **THEN** the response contains complexity entries for the valid files; no error response is returned; and no entry for `syntax_error.py` appears in `functions`

#### Scenario: over-bound file is skipped gracefully
- **WHEN** complexity is requested for a tree containing a file that exceeds the configured byte-size or AST depth cap
- **THEN** the over-bound file is silently skipped (diagnostic on stderr only); the remaining files' functions are returned normally

### Requirement: deterministic complexity output
The complexity result `functions` array SHALL be ordered by `(file, line, name)`. The analyzed file set SHALL be the ordered concatenation of the sorted `source_files` then `test_files`, de-duplicated preserving first occurrence (never a set union). Given identical input, the same `root_path` and `patterns` MUST produce byte-identical JSON-RPC output.

#### Scenario: consistent ordering across runs
- **WHEN** a `complexity` request is answered twice with identical inputs
- **THEN** the `functions` arrays in both responses are identical in order and content
