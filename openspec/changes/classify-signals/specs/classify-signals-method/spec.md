## ADDED Requirements

### Requirement: classify_signals method params
The `classify_signals` method SHALL accept a `params` object with a required string `root_path` and an optional `patterns` array of strings (the same shared params as `analyze`/`complexity`/`coverage`). If `params` is absent, is not an object, or lacks a string `root_path`, the server SHALL respond with `-32602` (invalid params). If `patterns` is present and is not an array of strings, the server SHALL respond with `-32602`.

#### Scenario: classify_signals accepts valid root_path and patterns
- **WHEN** a `classify_signals` request is sent with `params: {"root_path": "/abs/path", "patterns": ["./..."]}`
- **THEN** a valid result is returned

#### Scenario: classify_signals rejects missing root_path
- **WHEN** a `classify_signals` request is sent with `params: {}`
- **THEN** a `-32602` error is returned

#### Scenario: classify_signals rejects non-string root_path
- **WHEN** a `classify_signals` request is sent with `params: {"root_path": 123}`
- **THEN** a `-32602` error is returned

#### Scenario: classify_signals rejects non-array patterns
- **WHEN** a `classify_signals` request is sent with `params: {"root_path": "/abs/path", "patterns": "**/*.py"}`
- **THEN** a `-32602` error is returned

### Requirement: classify_signals result schema
The `classify_signals` method SHALL return a result object with a `signals` array. Each signal SHALL carry the exact protocol v1.1.0 field names `function`, `package`, `side_effect_type`, `source`, and `weight`, and SHALL carry a short, non-empty `reasoning`. `function` SHALL be the unqualified function name and `package` the dotted package (NOT a `name` field). `weight` SHALL be an integer. No signal object SHALL carry a `classification` field or any `contractual`/`incidental`/`ambiguous` label.

#### Scenario: result is a signals array with protocol fields
- **WHEN** a `classify_signals` request is answered for a tree with at least one matching function-effect pair
- **THEN** the result has a `signals` array whose entries each contain `function`, `package`, `side_effect_type`, `source`, integer `weight`, and a short, non-empty `reasoning`

#### Scenario: signals use function and package not name
- **WHEN** a signal is returned for the function `divide` in package `math_utils`
- **THEN** the object has `function == "divide"` and `package == "math_utils"` and has no `name` key

#### Scenario: signals omit classification
- **WHEN** a `classify_signals` result contains any signal
- **THEN** no signal object contains a `classification` key or any classification label value

### Requirement: source field is one of exactly five values
Every signal's `source` field SHALL be exactly one of `interface`, `visibility`, `caller_count`, `naming_convention`, or `docstring`. No other `source` value SHALL appear.

#### Scenario: only allowed source strings appear
- **WHEN** a `classify_signals` result contains signals
- **THEN** each signal's `source` is one of `interface`, `visibility`, `caller_count`, `naming_convention`, `docstring`

### Requirement: classify_signals maps missing root to -32602
The `classify_signals` method SHALL translate a missing or non-directory `root_path` (surfaced as `FileNotFoundError` by the discovery layer) into a `-32602` invalid params error, mirroring the other analysis methods.

#### Scenario: nonexistent root via RPC
- **WHEN** a `classify_signals` request is sent with a nonexistent `root_path`
- **THEN** a `-32602` error is returned

### Requirement: classify_signals capability flag is advertised true
The `initialize` result SHALL advertise `capabilities.classify_signals: true`, matching the now-implemented method. The `discover` flag SHALL stay `true`; `test_mapping` and `streaming` SHALL stay `false`.

#### Scenario: initialize advertises classify_signals true
- **WHEN** `initialize` is called
- **THEN** `capabilities` is `{discover: true, test_mapping: false, classify_signals: true, streaming: false}`

### Requirement: classify_signals is registered and no longer method-not-found
The `classify_signals` method SHALL be registered in the server dispatch so it no longer returns `-32601`. A valid request SHALL return a result object rather than a method-not-found error.

#### Scenario: classify_signals no longer method-not-found
- **WHEN** a `classify_signals` request with valid params is sent
- **THEN** the response is a result containing a `signals` array, not a `-32601` method-not-found error

### Requirement: deterministic classify_signals output
The `classify_signals` method SHALL produce deterministic output: the same input tree with identical params MUST produce byte-identical JSON-RPC output across repeated invocations, inheriting the detector's deterministic function and effect ordering.

#### Scenario: two calls over the same tree produce identical results
- **WHEN** a `classify_signals` request is sent twice over the same fixture tree with identical params
- **THEN** both responses are byte-identical in their `signals` arrays, including ordering

### Requirement: supersedes prior capability assertions on archive
This change flips `capabilities.classify_signals` from `false` to `true`. Three prior changes are not yet archived and each carry an `initialize` capability snapshot that will land in `openspec/specs/` on archive: `scaffold-and-protocol` (protocol capability — all four flags `false`), `taxonomy-and-discovery` (discover-method — `classify_signals: false`), and `analysis-methods` (#4, analyze-method — `classify_signals: false`). Because OpenSpec archival is sequential, the latest archived `initialize` snapshot governs; this change is archived after those three, so its `classify_signals: true` assertion supersedes each prior `false` assertion. No separate MODIFIED spec block is required while those changes remain unarchived. This reconciliation is recorded so that archiving the full chain does not leave conflicting `initialize` capability scenarios in `openspec/specs/`.

#### Scenario: capability transition is reconciled across the unarchived chain
- **WHEN** `scaffold-and-protocol`, `taxonomy-and-discovery`, change #4 (analysis-methods), and this change (classify-signals) are all archived in sequence
- **THEN** the effective `initialize` capability for `classify_signals` is `true`, with no contradictory `false` assertion remaining from any earlier change in the chain
