## ADDED Requirements

### Requirement: parse_coverage public API
The system SHALL provide `parse_coverage(root_path: str, patterns: list[str]) -> list[dict]` that reads existing coverage data and maps it to functions. It SHALL NOT run pytest and SHALL NOT invoke `coverage run`; it reads data only.

#### Scenario: parse_coverage reads existing data only
- **WHEN** `parse_coverage` is called on a project containing pre-generated coverage data
- **THEN** it returns coverage entries without executing the analyzed project's tests

### Requirement: coverage data lookup order
`parse_coverage` SHALL look for coverage data in this order: first `root_path/coverage.json` (a coverage.py JSON report), then `root_path/.coverage` (the default coverage.py data file). When a `coverage.json` is present it SHALL be parsed with the standard-library `json` module using `files.<path>.executed_lines` and `files.<path>.missing_lines`. When only `.coverage` is present it SHALL be read via `coverage.Coverage(data_file=...).load()` then `Coverage.analysis2(filename)`, which returns executable statements and missing lines so that `total_stmts` is directly computable; `CoverageData.lines()` MUST NOT be used for this branch because it returns only executed lines and would force an artificially high percentage.

#### Scenario: coverage.json preferred when present
- **WHEN** both `coverage.json` and `.coverage` exist under `root_path`
- **THEN** `parse_coverage` uses `coverage.json`

#### Scenario: .coverage used when only it exists
- **WHEN** only `.coverage` exists under `root_path`
- **THEN** `parse_coverage` loads it via `coverage.Coverage(data_file=...).load()` and calls `Coverage.analysis2(filename)` (not `get_data().lines()`) to obtain executable statements and missing lines

### Requirement: missing coverage data returns empty
When neither `coverage.json` nor `.coverage` exists under `root_path`, `parse_coverage` SHALL return an empty list of functions rather than raising an error.

#### Scenario: no coverage files present
- **WHEN** `parse_coverage` runs over a project with no `coverage.json` and no `.coverage`
- **THEN** it returns an empty functions list and does not raise

### Requirement: line-to-function mapping and coverage math
`parse_coverage` SHALL map covered and missing lines to functions using AST function spans `[start_line, end_line]` (body lines inclusive). Each entry SHALL carry `file`, `function`, `start_line`, `end_line`, `covered_stmts`, `total_stmts`, and `percentage`. For the `coverage.json` branch, `total_stmts` SHALL be derived from `executed_lines` and `missing_lines` within the span; `covered_stmts` SHALL count executed lines within the span. For the `.coverage` branch, `total_stmts` and `missing_stmts` are obtained directly from `Coverage.analysis2(filename)` output scoped to the span. `covered_stmts` SHALL count those statement lines that were executed; `percentage` SHALL be `round(covered_stmts / total_stmts * 100, 1)` when `total_stmts > 0` and `0.0` otherwise. The function field SHALL be named `function`, not `name`.

#### Scenario: covered and total computed for a function
- **WHEN** `parse_coverage` maps a canned `coverage.json` against a small module
- **THEN** the entry for the module's function reports the expected `covered_stmts` and `total_stmts`

#### Scenario: percentage is a rounded float
- **WHEN** a function has 3 covered of 4 total statement lines
- **THEN** the entry `percentage` is `75.0`

#### Scenario: zero total yields zero percentage
- **WHEN** a function span contains no statement lines
- **THEN** `total_stmts` is `0` and `percentage` is `0.0`

### Requirement: coverage confines to the discovered set
`parse_coverage` SHALL call `discover(root_path, patterns)` first and map coverage data ONLY for files present in the discovered set. Any path key from `coverage.json` MUST be `resolve()`d and verified to be contained within `root_path` before use; a key that escapes `root_path` (e.g. `../../etc/passwd`) MUST be silently ignored and never opened. `coverage.json` path keys MUST be normalized to root-relative POSIX paths for lookup. A nonexistent `root_path` SHALL raise `FileNotFoundError`, which the caller maps to `-32602`, before any file lookup is attempted. A WHOLE-DATAFILE load/parse failure — `json.JSONDecodeError` for `coverage.json`, `sqlite3.DatabaseError` for `.coverage`, or a top-level `CoverageException` raised by `load()`, or a structural mismatch such as missing `files` key, `files` not being a mapping, or an entry missing `executed_lines`/`missing_lines` (i.e. JSON-valid but wrong-shape) — SHALL cause `parse_coverage` to return an empty list `[]`.

#### Scenario: path traversal key is ignored
- **WHEN** `parse_coverage` processes a `coverage.json` containing a key such as `../../etc/passwd`
- **THEN** that key is ignored entirely; no attempt is made to open or map the path; only files within `root_path` appear in the result

#### Scenario: malformed coverage.json produces empty result
- **WHEN** `parse_coverage` encounters a `coverage.json` that is not valid JSON
- **THEN** it catches `json.JSONDecodeError` and returns an empty list `[]` without raising

#### Scenario: JSON-valid but wrong-shape coverage.json produces empty result
- **WHEN** `parse_coverage` encounters a `coverage.json` that is valid JSON but has wrong structure (e.g. missing `files` key, `files` is not a mapping, or an entry is missing `executed_lines`/`missing_lines`)
- **THEN** it catches the structural error (`KeyError`, `TypeError`) and returns an empty list `[]` without raising

### Requirement: coverage skips parse-error and over-bound files
When building AST spans for mapped files, `parse_coverage` SHALL skip any file that raises `(SyntaxError, ValueError, RecursionError, OSError, MemoryError)` during parsing and continue with the remaining files. A per-file byte-size cap of `MAX_FILE_BYTES = 16 MiB` (fixed constant, not user-configurable in v1) enforced via `stat` before `open()` (regular-file-only; any candidate that is not `S_ISREG` MUST be skipped with a stderr diagnostic) and a fixed AST-depth/recursion budget MUST bound AST analysis; a file exceeding either bound MUST be skipped-and-continued. For the `.coverage` branch, each candidate MUST pass the `S_ISREG` check and byte-cap before `Coverage.analysis2()` is called; the `analysis2()` call MUST be wrapped in `(SyntaxError, ValueError, RecursionError, OSError, MemoryError)` PLUS CoverageException subclasses (`NoSource`, `NotPython`) — any of these causes that ONE file to be skipped-and-continued and does NOT produce an empty whole result. In all skip cases a per-file diagnostic MUST go to stderr; it MUST NOT appear in the stdout JSON-RPC result.

#### Scenario: parse error during AST span building is skipped
- **WHEN** `parse_coverage` processes a tree that includes a file with a syntax error alongside valid files that have coverage data
- **THEN** the syntax-error file is skipped (diagnostic on stderr only); valid files' function coverage entries are returned normally

#### Scenario: per-file CoverageException does not zero the result
- **WHEN** `parse_coverage` processes coverage data referencing several files where one source is unresolvable (e.g. raises `NoSource` or `NotPython` from `Coverage.analysis2()`)
- **THEN** that one file is skipped with a stderr diagnostic; `parse_coverage` still returns entries for the other files

### Requirement: deterministic coverage output
The list returned by `parse_coverage` SHALL be ordered by `(file, start_line, function)`. The analyzed file set SHALL be the ordered concatenation of the sorted `source_files` then `test_files`, de-duplicated preserving first occurrence (never a set union). Given identical input, the same `root_path` and `patterns` MUST produce byte-identical JSON-RPC output.

#### Scenario: consistent ordering across calls
- **WHEN** `parse_coverage` is called twice with identical inputs
- **THEN** the returned lists are identical in order and content
