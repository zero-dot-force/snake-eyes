## ADDED Requirements

### Requirement: analyze method params
The `analyze` method SHALL accept a `params` object with a required string `root_path` and an optional `patterns` array of strings (patterns select Python files under `root_path`; the Go-style `"./..."` pattern means the whole tree). If `params` is absent, is not an object, or lacks a string `root_path`, the server SHALL respond with `-32602` (invalid params). If `patterns` is present and is not an array of strings, the server SHALL respond with `-32602`.

#### Scenario: analyze accepts valid root_path and patterns
- **WHEN** an `analyze` request is sent with `params: {"root_path": "/abs/path", "patterns": ["./..."]}` (`"./..."` selects all Python files under root)
- **THEN** a valid result is returned

#### Scenario: analyze rejects missing root_path
- **WHEN** an `analyze` request is sent with `params: {}`
- **THEN** a `-32602` error is returned

#### Scenario: analyze rejects non-string root_path
- **WHEN** an `analyze` request is sent with `params: {"root_path": 123}`
- **THEN** a `-32602` error is returned

#### Scenario: analyze rejects non-array patterns
- **WHEN** an `analyze` request is sent with `params: {"root_path": "/abs/path", "patterns": "**/*.py"}`
- **THEN** a `-32602` error is returned

### Requirement: analyze result schema
The `analyze` method SHALL return a result object with a `functions` array. Each function SHALL carry `name`, `package`, `file`, `line`, and `side_effects`. The `file` field SHALL be a root-relative POSIX path (the same root-relative POSIX paths produced by the shared `discovery`/`ordered_file_list` layer used by all three modules), so `(file, function)` joins have parity with complexity and coverage results. Each entry in `side_effects` SHALL always carry `type`, `description`, and `location`; `target` and `detail` are OPTIONAL and SHALL be omitted when not applicable. The `location` path prefix SHALL also be root-relative POSIX (consistent with the `file` field). The optional `detail` object carries Python-specific metadata only (e.g. `{"confidence": "ambiguous"}` or `{"exception_class": "ZeroDivisionError"}`). No effect object SHALL carry a `classification` field (Gaze performs classification). `location` SHALL be formatted `"<file>.py:<line>:<col>"`.

#### Scenario: result shape with target
- **WHEN** an `analyze` request is answered for a function with one effect that has a natural target (e.g. a `ReceiverMutation`)
- **THEN** the result has a `functions` array whose entry contains `name`, `package`, `file`, `line`, and a `side_effects` array of objects each with `type`, `description`, `location`, and optionally `target`

#### Scenario: result shape without target
- **WHEN** an `analyze` request is answered for a function with a `ReturnValue` effect
- **THEN** the effect object contains `type`, `description`, and `location` but does NOT contain a `target` key

#### Scenario: effects omit classification
- **WHEN** an `analyze` result contains any effect
- **THEN** no effect object contains a `classification` key

### Requirement: package field follows shared derivation
The `package` field of each function in the result SHALL be derived by the shared package-identity helper: strip `.py` from the file path relative to `root_path`, replace `'/'` with `'.'`, and drop a trailing `.__init__` (so `pkg/__init__.py` → `"pkg"`). This is the same `derive_package` helper used by the detector and complexity modules only; coverage result rows carry `file` + `function` (no `package`) per the protocol schema, so coverage does NOT use it.

#### Scenario: pkg/__init__.py package is pkg
- **WHEN** an `analyze` request covers `pkg/__init__.py` under `root_path`
- **THEN** each function in that file has `package == "pkg"` in the result

#### Scenario: nested module has dotted package
- **WHEN** an `analyze` request covers `pkg/sub/mod.py` under `root_path`
- **THEN** each function in that file has `package == "pkg.sub.mod"` in the result

### Requirement: analyze skips parse-error files
The `analyze` method SHALL skip files that fail to parse due to `SyntaxError`, `ValueError`, `RecursionError`, `OSError` (e.g. `PermissionError` on read), or `MemoryError` (raised during AST traversal) and continue, returning the functions of the valid files in the same request. The broadened skip tuple applied by `analyze` is `(SyntaxError, ValueError, RecursionError, OSError, MemoryError)`. A file that exceeds the configured byte-size cap (`MAX_FILE_BYTES`) or AST depth / recursion budget (`MAX_AST_DEPTH`) MUST also be skipped-and-continued; a per-file diagnostic MUST go to stderr and MUST NOT appear in the JSON-RPC result; the result MUST NOT include an errors array. The result schema SHALL NOT include an `errors` array. Each skipped file SHALL emit a diagnostic to stderr, never to the JSON-RPC result stream.

#### Scenario: mixed valid and invalid files
- **WHEN** an `analyze` request targets a tree containing both a syntax-error file and a valid file
- **THEN** the valid file's functions are present in the result and no error response is returned

#### Scenario: ValueError in parse handled gracefully
- **WHEN** an `analyze` request targets a tree containing a file that raises `ValueError` during `ast.parse` and a valid file
- **THEN** the valid file's functions are present in the result, the erroneous file contributes no entries, and the response is a result (not an error)

### Requirement: analyze maps FileNotFoundError to -32602
The `analyze` method SHALL translate a missing or non-directory `root_path` into a `-32602` invalid params error.

#### Scenario: nonexistent root via RPC
- **WHEN** an `analyze` request is sent with a nonexistent `root_path`
- **THEN** a `-32602` error is returned

### Requirement: Deterministic analyze output
The `analyze` method SHALL produce deterministic output. `functions[]` SHALL be ordered by `(file, line, name)`. `side_effects[]` within each function SHALL be ordered by `(line, col, type)`. The analyzed file set is the ordered concatenation of the sorted `source_files` then `test_files`, de-duplicated preserving first occurrence (never a set union). The same input tree MUST produce byte-identical JSON-RPC output across repeated invocations.

#### Scenario: two analyze calls over the same tree produce identical results
- **WHEN** an `analyze` request is sent twice over the same fixture tree with identical params
- **THEN** both responses are byte-identical in their `functions` arrays, including ordering of functions and their `side_effects`

### Requirement: analyze is a required method not a capability flag
The `analyze` method SHALL be registered in the server dispatch so it no longer returns `-32601`. Registering it SHALL NOT change any `initialize` capability flag; `discover` stays `true` and `test_mapping`, `classify_signals`, and `streaming` stay `false`.

#### Scenario: analyze no longer method-not-found
- **WHEN** an `analyze` request with valid params is sent
- **THEN** the response is a result, not a `-32601` method-not-found error

#### Scenario: initialize capabilities unchanged
- **WHEN** `initialize` is called
- **THEN** `capabilities` is `{discover: true, test_mapping: false, classify_signals: false, streaming: false}`
