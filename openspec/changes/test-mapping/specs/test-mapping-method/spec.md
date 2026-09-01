## ADDED Requirements

### Requirement: test_mapping JSON-RPC method

The server SHALL expose a `test_mapping` JSON-RPC method that accepts a params object of the form `{"root_path": <absolute string>, "patterns": <list of strings>}` and returns a result object `{"mappings": [...]}` conforming to Gaze analyzer protocol v1.1.0. The method SHALL be registered in the server dispatch table under the key `"test_mapping"`.

#### Scenario: Valid request returns a mappings envelope
- **WHEN** a `test_mapping` request is dispatched with a valid `root_path` and `patterns`
- **THEN** the result is an object whose sole top-level key is `mappings`, and its value is a JSON array

#### Scenario: Project with no tests returns empty mappings
- **WHEN** a `test_mapping` request targets a root that contains no test files
- **THEN** the result is `{"mappings": []}` returned as a success result, not a JSON-RPC error

#### Scenario: Project with no test/target pairs returns empty mappings
- **WHEN** test files exist but none can be paired to a production function
- **THEN** the result is `{"mappings": []}` returned as a success result, not a JSON-RPC error

### Requirement: Capability advertisement

The `initialize` result SHALL advertise `test_mapping` as `true`, while leaving `discover` and `classify_signals` as `true` and `streaming` as `false`.

#### Scenario: initialize reports test_mapping enabled
- **WHEN** an `initialize` request is handled
- **THEN** the returned `capabilities` object contains `test_mapping: true`, `discover: true`, `classify_signals: true`, and `streaming: false`

### Requirement: Parameter validation and error mapping

The `test_mapping` handler SHALL validate params using the shared analysis-params validator and SHALL return JSON-RPC error code `INVALID_PARAMS` (-32602) when params are not an object, `root_path` is not a string, `patterns` is not a list of strings, or the resolved root path does not exist.

#### Scenario: Missing root_path is rejected
- **WHEN** a `test_mapping` request omits `root_path` or provides a non-string `root_path`
- **THEN** the server responds with JSON-RPC error code -32602 (INVALID_PARAMS)

#### Scenario: Non-existent root path is rejected
- **WHEN** a `test_mapping` request provides a `root_path` that is not an existing directory
- **THEN** the pipeline's `FileNotFoundError` is mapped to JSON-RPC error code -32602 (INVALID_PARAMS)

### Requirement: Mapping row field contract

Each element of `mappings` SHALL be an object containing the keys `test_function`, `test_file`, `assertion_location`, `assertion_type`, `target_function`, `target_package`, `side_effect_type`, and `confidence`. `confidence` SHALL be an integer in the inclusive range 0–100. `assertion_type` SHALL be exactly one of `equality`, `error_check`, `membership`, `identity`, `comparison`, or `generic`. `assertion_location` SHALL be formatted `path:line` with the path relative to `root_path`. `test_file` and every path-valued field SHALL be a POSIX path relative to `root_path`, consistent with `assertion_location`, so that output is independent of the absolute location of the analyzed project. For a test defined as a method of a `unittest.TestCase` subclass, `test_function` SHALL be class-qualified as `ClassName.method_name` (e.g. `T.test_x`); for a top-level test function it SHALL be the bare function name. This keeps the de-duplication key unambiguous when two same-named `test_*` methods are defined in different classes within one file.

#### Scenario: Row carries all required keys with correct types
- **WHEN** a mapping row is produced for a paired test assertion
- **THEN** the row contains every required key, `confidence` is an integer in [0, 100], and `assertion_type` is one of the six allowed values

#### Scenario: assertion_location is a root-relative path with a line number
- **WHEN** a mapping row references an assertion at a given source line
- **THEN** `assertion_location` equals `<relative_path>:<line>` with no column component

#### Scenario: test_file is a root-relative path
- **WHEN** a mapping row references a test defined under `root_path`
- **THEN** `test_file` is a POSIX path relative to `root_path` with no absolute prefix

### Requirement: Supersedes prior capability assertions on archive

Because OpenSpec archival is sequential, the latest archived `initialize` snapshot governs the effective capability set. This change's `test_mapping: true` SHALL supersede the `test_mapping: false` assertions carried by the prior unarchived changes (`scaffold-and-protocol`, `taxonomy-and-discovery`, `analysis-methods`, and `classify-signals`). This reconciliation is recorded so that archiving the full chain does not leave conflicting `initialize` capability scenarios in `openspec/specs/`.

#### Scenario: Latest archived capability snapshot wins
- **WHEN** this change is archived after `classify-signals`
- **THEN** the governing `initialize` capability snapshot advertises `test_mapping: true`, superseding every prior `test_mapping: false` assertion
