## ADDED Requirements

### Requirement: complexity method params
The `complexity` method SHALL accept a `params` object with a required string `root_path` and an optional `patterns` array of strings. If `params` is absent, is not an object, or lacks a string `root_path`, the server SHALL respond with `-32602` (invalid params). If `patterns` is present and is not an array of strings, the server SHALL respond with `-32602`.

#### Scenario: complexity accepts valid params
- **WHEN** a `complexity` request is sent with `params: {"root_path": "/abs/path", "patterns": ["./..."]}`
  (`./...` selects all Python files under `root_path`; it is equivalent to the whole-tree pattern)
- **THEN** a valid result is returned

#### Scenario: complexity rejects missing root_path
- **WHEN** a `complexity` request is sent with `params: {}`
- **THEN** a `-32602` error is returned

#### Scenario: complexity rejects non-string root_path
- **WHEN** a `complexity` request is sent with `params: {"root_path": 42}`
- **THEN** a `-32602` error is returned

#### Scenario: complexity rejects non-array patterns
- **WHEN** a `complexity` request is sent with `params: {"root_path": "/abs/path", "patterns": "*.py"}`
- **THEN** a `-32602` error is returned

### Requirement: complexity result schema
The `complexity` method SHALL return a result object with a `functions` array. Each function SHALL carry `name`, `package`, `file`, `line`, and `complexity` (integer). `package` SHALL be the dotted module path derived from the file path relative to `root_path` (strip `.py`, replace `/` with `.`, drop a trailing `.__init__`).

#### Scenario: result shape
- **WHEN** a `complexity` request is answered for a module `pkg/mod.py` defining `f`
- **THEN** the result `functions` entry is `{name: "f", package: "pkg.mod", file: "pkg/mod.py", line: <int>, complexity: <int>}`

#### Scenario: package for package init
- **WHEN** a `complexity` request covers a function in `pkg/__init__.py`
- **THEN** the entry `package` is `pkg`

### Requirement: complexity skips parse-error files
The `complexity` method SHALL skip files that raise `(SyntaxError, ValueError, RecursionError, OSError, MemoryError)` during parsing and continue, returning complexity entries for the valid files in the same request. A file that exceeds the configured byte-size cap (`MAX_FILE_BYTES = 16 MiB`) or AST depth / recursion budget MUST also be skipped-and-continued. In all skip cases a per-file diagnostic MUST go to stderr; the result MUST NOT include an `errors` array.

#### Scenario: mixed valid and invalid files
- **WHEN** a `complexity` request targets a tree containing both a syntax-error file and a valid file
- **THEN** the valid file's functions have complexity entries and no error response is returned

### Requirement: deterministic complexity result
The `complexity` method result `functions` array SHALL be ordered by `(file, line, name)`. The analyzed file set SHALL be the ordered concatenation of the sorted `source_files` then `test_files`, de-duplicated preserving first occurrence (never a set union). Given identical input, the same `root_path` and `patterns` MUST produce byte-identical JSON-RPC output.

#### Scenario: consistent ordering across calls
- **WHEN** a `complexity` request is answered twice with identical inputs
- **THEN** the `functions` arrays in both responses are identical in order and content

### Requirement: complexity maps FileNotFoundError to -32602
The `complexity` method SHALL translate a missing or non-directory `root_path` into a `-32602` invalid params error.

#### Scenario: nonexistent root via RPC
- **WHEN** a `complexity` request is sent with a nonexistent `root_path`
- **THEN** a `-32602` error is returned

### Requirement: complexity is a required method not a capability flag
The `complexity` method SHALL be registered in the server dispatch so it no longer returns `-32601`. Registering it SHALL NOT change any `initialize` capability flag.

#### Scenario: complexity no longer method-not-found
- **WHEN** a `complexity` request with valid params is sent
- **THEN** the response is a result, not a `-32601` method-not-found error
