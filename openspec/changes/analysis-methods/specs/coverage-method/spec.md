## ADDED Requirements

### Requirement: coverage method params
The `coverage` method SHALL accept a `params` object with a required string `root_path` and an optional `patterns` array of strings. If `params` is absent, is not an object, or lacks a string `root_path`, the server SHALL respond with `-32602` (invalid params). If `patterns` is present and is not an array of strings, the server SHALL respond with `-32602`.

#### Scenario: coverage accepts valid params
- **WHEN** a `coverage` request is sent with `params: {"root_path": "/abs/path", "patterns": ["./..."]}`
  (`./...` selects all Python files under `root_path`; it is equivalent to the whole-tree pattern)
- **THEN** a valid result is returned

#### Scenario: coverage rejects missing root_path
- **WHEN** a `coverage` request is sent with `params: {}`
- **THEN** a `-32602` error is returned

#### Scenario: coverage rejects non-string root_path
- **WHEN** a `coverage` request is sent with `params: {"root_path": 42}`
- **THEN** a `-32602` error is returned

#### Scenario: coverage rejects non-array patterns
- **WHEN** a `coverage` request is sent with `params: {"root_path": "/abs/path", "patterns": "*.py"}`
- **THEN** a `-32602` error is returned

### Requirement: coverage result schema
The `coverage` method SHALL return a result object with a `functions` array (the handler wraps `parse_coverage`'s bare list into `{"functions": [...]}`). Each entry SHALL carry `file`, `function`, `start_line`, `end_line`, `covered_stmts`, `total_stmts`, and `percentage`. The function-name field SHALL be `function`, not `name`. `percentage` SHALL be a float in the range 0.0–100.0. The `file` field SHALL be a **root-relative POSIX path** so that Gaze can join coverage entries to analyze/complexity entries by `(file, function)`, disambiguated by `start_line` when nested names repeat within a file.

#### Scenario: result shape
- **WHEN** a `coverage` request is answered against a project with canned coverage data
- **THEN** each `functions` entry contains `file`, `function`, `start_line`, `end_line`, `covered_stmts`, `total_stmts`, and a float `percentage`

#### Scenario: function field name
- **WHEN** a `coverage` result entry is inspected
- **THEN** it uses the key `function` and does not use the key `name`

### Requirement: coverage returns empty when data is absent
The `coverage` method SHALL return `{"functions": []}` when neither `coverage.json` nor `.coverage` exists under `root_path`, rather than an error.

#### Scenario: no coverage data present
- **WHEN** a `coverage` request targets a project with no coverage data files
- **THEN** the result is `{"functions": []}` and no error response is returned

### Requirement: nonexistent root validated before coverage file lookup
The `coverage` handler SHALL validate `root_path` existence by invoking `discover()` (or an equivalent existence check) BEFORE attempting any coverage file lookup. A nonexistent `root_path` SHALL raise `FileNotFoundError`, which the handler maps to a `-32602` invalid params error, before any attempt is made to open `coverage.json` or `.coverage`. An existing `root_path` that has no coverage data SHALL return `{"functions": []}`.

#### Scenario: nonexistent root returns -32602
- **WHEN** a `coverage` request is sent with a `root_path` that does not exist on disk
- **THEN** a `-32602` error is returned and no file lookup is attempted

#### Scenario: existing root without coverage data returns empty
- **WHEN** a `coverage` request is sent with a `root_path` that exists but contains neither `coverage.json` nor `.coverage`
- **THEN** the result is `{"functions": []}` and no error is returned

### Requirement: coverage never runs tests
The `coverage` method SHALL only read existing coverage data and SHALL NOT run pytest or invoke `coverage run`.

#### Scenario: coverage reads data only
- **WHEN** a `coverage` request is answered
- **THEN** no test suite is executed and no coverage collection is triggered

### Requirement: coverage skips parse-error files
The `coverage` method SHALL skip any file that raises `(SyntaxError, ValueError, RecursionError, OSError, MemoryError)` during AST parsing (when building function spans) and continue processing remaining files. Only regular files (verified via `stat`; non-`S_ISREG` paths skipped with a stderr diagnostic) are read, consistent with the coverage-parser layer. A file that exceeds the configured byte-size cap (`MAX_FILE_BYTES = 16 MiB`) or AST depth / recursion budget MUST also be skipped-and-continued. In all skip cases a per-file diagnostic MUST go to stderr; the result MUST NOT include an `errors` array.

#### Scenario: syntax-error file is skipped gracefully
- **WHEN** a `coverage` request targets a tree containing a syntax-error file alongside valid files with coverage data
- **THEN** the syntax-error file is skipped (diagnostic on stderr only); valid files' function coverage entries are returned normally

### Requirement: deterministic coverage result
The `coverage` method result `functions` array SHALL be ordered by `(file, start_line, function)`. The sort key matches the ordering guaranteed by `parse_coverage`. The analyzed file set SHALL be the ordered concatenation of the sorted `source_files` then `test_files`, de-duplicated preserving first occurrence (never a set union). Given identical input, the same `root_path` and `patterns` MUST produce byte-identical JSON-RPC output.

#### Scenario: consistent ordering across calls
- **WHEN** a `coverage` request is answered twice with identical inputs
- **THEN** the `functions` arrays in both responses are identical in order and content

### Requirement: coverage is a required method not a capability flag
The `coverage` method SHALL be registered in the server dispatch so it no longer returns `-32601`. Registering it SHALL NOT change any `initialize` capability flag.

#### Scenario: coverage no longer method-not-found
- **WHEN** a `coverage` request with valid params is sent
- **THEN** the response is a result, not a `-32601` method-not-found error
