## ADDED Requirements

### Requirement: discover method params
The `discover` method SHALL accept a `params` object with a required string `root_path` and an optional `patterns` array of strings. If `params` is absent, is not an object, or lacks a string `root_path`, the server SHALL respond with `-32602` (invalid params).

#### Scenario: discover accepts root_path and patterns
- **WHEN** a `discover` request is sent with `params: {"root_path": "/abs/path", "patterns": ["./..."]}`
- **THEN** a valid result is returned

#### Scenario: discover accepts missing patterns
- **WHEN** a `discover` request is sent with `params: {"root_path": "/abs/path"}`
- **THEN** a valid result is returned

#### Scenario: discover rejects missing root_path
- **WHEN** a `discover` request is sent with `params: {}`
- **THEN** a `-32602` error is returned

#### Scenario: discover rejects non-string root_path
- **WHEN** a `discover` request is sent with `params: {"root_path": 123}`
- **THEN** a `-32602` error is returned

#### Scenario: discover rejects non-object params
- **WHEN** a `discover` request is sent with array `params`
- **THEN** a `-32602` error is returned

#### Scenario: discover rejects non-array patterns
- **WHEN** a `discover` request is sent with `params: {"root_path": "/abs/path", "patterns": "src"}`
- **THEN** a `-32602` error is returned

### Requirement: discover result schema
The `discover` method SHALL return a result object with exactly `source_files` (array of strings) and `test_files` (array of strings), each relative to `root_path`, and each list ordered deterministically (lexicographic by POSIX path).

#### Scenario: result shape
- **WHEN** a `discover` request is answered against a project with `src/foo.py` and `tests/test_foo.py`
- **THEN** the result is `{"source_files": ["src/foo.py"], "test_files": ["tests/test_foo.py"]}`

### Requirement: discover maps FileNotFoundError to -32602
The `discover` method SHALL translate a missing or non-directory `root_path` into a `-32602` invalid params error.

#### Scenario: nonexistent root via RPC
- **WHEN** a `discover` request is sent with a nonexistent `root_path`
- **THEN** a `-32602` error is returned

### Requirement: initialize advertises discover capability
The `initialize` method SHALL report `capabilities.discover` as `true` and leave `test_mapping`, `classify_signals`, and `streaming` as `false`.

#### Scenario: discover flag flipped
- **WHEN** `initialize` is called
- **THEN** `capabilities.discover` is `true` and the other three capability flags are `false`
