## Context

`gaze quality --analyzer snake-eyes --language python .` reports
`Assertion detection confidence: 0%` because Gaze's external-analyzer
adapter (`internal/adapter/quality.go`) hardcodes
`AssertionDetectionConfidence: 0` — only Gaze's native Go analyzer
computes the value. Snake-eyes already performs the assertion detection
(`quality/assertions.py`), but discards the aggregate: `collect_assertions`
runs only inside the pairing loop in `quality/pipeline.py`, and the
`test_mapping` response carries only `{"mappings": [...]}`.

Issue #17 proposes adding `assertion_detection_confidence` (int, 0–100)
to the `test_mapping` response, computed as the fraction of test
functions where at least one assertion was detected. This change is
snake-eyes-side only; Gaze will consume the new field once present.

Constraint: the constitution requires deterministic, byte-identical
output and backward-compatible protocol changes (additive field only).

## Goals / Non-Goals

**Goals:**
- Emit `assertion_detection_confidence` in every successful
  `test_mapping` response.
- Compute the value from assertion detection over **all** collected test
  functions (paired and unpaired), so the analyzer's true knowledge is
  reflected.
- Preserve deterministic output and the existing `mappings` schema.

**Non-Goals:**
- No Gaze-side changes (adapter reads the field in a separate effort).
- No changes to mapping-row fields, pairing, or effect-type inference.
- No capability negotiation change (`test_mapping` stays `true`). The
  additive `assertion_detection_confidence` field is a forward-compatible
  extension: the protocol has no field-level negotiation mechanism, older
  Gaze versions ignore the unknown key during JSON decoding, and the
  `mappings` contract still conforms to v1.1.0. This is the documented
  Conflict Resolution for Principle I (Governance).
- No new dependencies.

## Decisions

### D1 — Add the field to the response envelope (Issue Option 1)

The `test_mapping` result object becomes
`{"mappings": [...], "assertion_detection_confidence": <int>}`.

- **Rationale**: The analyzer holds assertion-detection data for every
  collected test function, including unpaired tests that never appear in
  `mappings`; Gaze cannot reconstruct that from mapping rows alone. The
  issue author prefers this option for that reason.
- **Alternatives considered**: Gaze-side computation from mapping data
  (Option 2) — rejected because it under-counts unpaired tests and blurs
  the analyzer's knowledge; keeping the value out entirely — rejected
  because it leaves the 0% report unfixed.

### D2 — Return a result object from the pipeline

Introduce a small `TestMappingResult` dataclass (in
`quality/pipeline.py`) with `mappings: list[dict[str, Any]]` and
`assertion_detection_confidence: int`. `run_test_mapping` returns this;
the server's `_test_mapping` handler builds the envelope.

- **Rationale**: Keeps the existing "pipeline returns data, server wraps
  into the JSON-RPC envelope" separation while carrying two values.
- **Alternatives considered**: returning a raw `tuple[list, int]` —
  rejected as less readable and less stable under future additions; a
  second `compute_confidence(...)` call — rejected because it would
  re-traverse the test ASTs, duplicating work.

### D3 — Integer arithmetic, round half up, 0 for empty

Confidence is `(100 * detected + total // 2) // total` when
`total > 0`, else `0`.

- **Rationale**: Pure integer math avoids floating-point nondeterminism
  and is trivially deterministic. `0` for the empty case is honest: with
  no collected test functions there is nothing to detect, matching the
  current 0% baseline.
- **Alternatives considered**: Python's `round()` (banker's rounding on
  floats) — rejected for float edge cases; floor division — rejected
  because half-up more closely matches user expectation for a percentage.

### D4 — Assertion collection promoted to a full test-function pass

Restructure `run_test_mapping` so that, after test-function collection,
the pipeline iterates every `(test_function, test_file)` pair, resolves
its AST node, and collects assertions once into a
`dict[tuple[str, str], list[AssertionInfo]]`. The pairing loop reads from
this map instead of re-collecting. The `not test_functions or
not target_records` and `not pairs` early returns are removed: pairing
still produces zero rows when appropriate, but confidence is computed
regardless. Assertion collection reuses the existing `collect_assertions`
guard: it swallows `RecursionError` internally and returns the assertions
collected before the depth budget (`MAX_AST_DEPTH`) was exceeded, so a
degenerate walk yields a partial list rather than an error. A test
function counts as "detected" iff its collected list is non-empty; a
function whose walk aborted before collecting any assertion counts as not
detected. The map is keyed by `(test_function, test_file)`, which assumes
test-function names are unique within a file (valid Python; a shadowed
duplicate `def` collapses to a single map entry, consistent with
`_get_func_node` resolving the same name to the last definition).

- **Rationale**: Confidence must account for unpaired tests, and a
  single collection pass avoids traversing the same AST twice.
- **Alternatives considered**: keep pairing-scoped collection and add a
  second dedicated pass for unpaired tests — rejected as wasteful and
  error-prone (two code paths for the same walk).

## Risks / Trade-offs

- **[Downstream tolerance]** Gaze's current adapter ignores the new key;
  the field is inert until Gaze reads it. The 0% report persists until a
  Gaze-side change lands. → Mitigation: additive field, no breaking
  change; the issue tracks the Gaze follow-up separately.
- **[Regression in envelope tests]** Tests asserting the exact
  `{"mappings": [...]}` shape fail. → Mitigation: update them in the same
  change (see tasks) and assert the new two-key envelope.
- **[Determinism]** Rounding and aggregation must be deterministic. →
  Mitigation: integer arithmetic only; no set iteration order
  dependencies (confidence is order-independent).
- **[Double traversal]** The new pass adds one assertion walk per test
  function that previously only ran for paired tests. → Mitigation: this
  replaces the pairing-loop walk rather than adding to it; net traversal
  is at most one extra walk per unpaired test function, bounded by the
  existing `MAX_AST_DEPTH` guard.
- **[Zero-production-target expansion]** Removing the
  `not target_records` half of the first early return means a project
  with many test files but no production targets now runs the assertion
  pass over every test function (previously it returned `[]` immediately).
  This is correct (confidence must reflect test functions regardless of
  targets) and still bounded by `MAX_FILE_BYTES` + `MAX_AST_DEPTH`.

## Migration Plan

- No data migration; purely an additive response field and an internal
  pipeline refactor.
- Rollback: revert the change; the `mappings` array is unchanged, so
  downstream consumers that ignore `assertion_detection_confidence`
  continue to work.

## Open Questions

- None blocking. The Gaze-side consumption of
  `assertion_detection_confidence` is out of scope and tracked in the
  upstream issue.
