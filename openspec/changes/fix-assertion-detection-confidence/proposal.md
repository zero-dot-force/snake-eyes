## Why

`gaze quality --analyzer snake-eyes --language python .` reports
`Assertion detection confidence: 0%` even though snake-eyes correctly
detects and classifies assertions across every collected test function. Gaze's
external-analyzer adapter (`internal/adapter/quality.go`) hardcodes
`AssertionDetectionConfidence: 0` for external analyzers, because only
Gaze's native Go analyzer computes that number internally. The analyzer
already holds the raw data needed to compute the value, so the fix
belongs in snake-eyes: extend the `test_mapping` response to carry the
confidence, which Gaze can then surface.

Ref: [GitHub Issue #17](https://github.com/zero-dot-force/snake-eyes/issues/17)

## What Changes

Add an `assertion_detection_confidence` field to the `test_mapping`
JSON-RPC response, computed by the analyzer as the percentage of
collected test functions in which at least one assertion was detected.

1. **Extend the `test_mapping` response envelope** — the result object
   becomes `{"mappings": [...], "assertion_detection_confidence": <int>}`
   where the new field is an integer in the inclusive range 0–100.

2. **Compute confidence over all test functions, not just paired ones** —
   the pipeline currently collects assertions only inside the pairing
   loop, so unpaired tests are invisible to the calculation. Assertion
   detection is promoted to a per-test-function pass that runs for every
   collected test function (pytest `test_*` functions and `unittest`
   `TestCase` methods), and the confidence is derived from that pass.

The change is snake-eyes-side only; no Gaze-side changes are in scope.
The field is informational — it does not affect contract coverage,
gap scores, or any existing mapping-row field.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-mapping-method`: the `test_mapping` response envelope gains a
  required `assertion_detection_confidence` integer field alongside
  `mappings`.

- `test-mapping-pipeline`: `run_test_mapping` now computes assertion
  detection confidence across all collected test functions and returns
  it to the server handler (which folds it into the response envelope).

## Impact

- **Protocol surface**: the `test_mapping` result object gains one
  top-level key. Downstream Gaze must tolerate the additional key; the
  existing `mappings` array and all row fields are unchanged.
  `assertion_detection_confidence` is an additive, forward-compatible
  extension of the pinned protocol v1.1.0: the `mappings` contract still
  conforms to v1.1.0, and older Gaze versions ignore the unknown key
  during JSON decoding. See the Protocol Fidelity note below for the
  capability-negotiation reconciliation.
- **Pipeline**: `run_test_mapping` returns a `TestMappingResult`
  dataclass carrying `mappings` and `assertion_detection_confidence`; the
  server handler folds it into the response envelope. Assertion
  collection is restructured from pairing-scoped to test-function-scoped.
- **Edge cases**: projects with no test functions yield a defined
  confidence (0), preserving deterministic output.
- **Constitution**: no JSON-RPC method additions, no new dependencies,
  no executed code. The additive field is reconciled against the
  capability-negotiation clause (see Constitution Alignment).
- **Documentation**: none required — README.md and AGENTS.md do not
  enumerate the `test_mapping` response envelope, so the additive field
  needs no doc change.
- **Existing tests**: `tests/test_test_mapping_method.py` asserts the
  exact `test_mapping` envelope and will be updated to the new two-key
  shape; `tests/test_server.py` and `tests/test_protocol.py` will be
  updated only if they assert the envelope (the capability `true` flag is
  unchanged).

## Constitution Alignment

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Protocol Fidelity | PASS | Additive field on an existing response; deterministic integer, no timestamps/randomness. Key ordering stable via `sort_keys`. Backward-compatible: `mappings` unchanged. The constitution's capability-negotiation clause is reconciled as follows: the protocol has no field-level negotiation mechanism, and older Gaze versions tolerate the unknown key during JSON decoding, so the additive field maintains backward compatibility without a capability-negotiation change (documented Conflict Resolution, Governance). |
| II. Detection Accuracy | PASS | Replaces a hardcoded 0 with a value derived from real detection data over every collected test function, including unpaired tests invisible to Gaze. |
| III. Python-Native Analysis | PASS | Uses existing `ast`-based assertion walk; no reimplementation, no new dependencies. |
| IV. Testability | PASS | Confidence computation is pure and unit-testable; conformance scenarios cover paired, unpaired, and empty projects. |
| V. Analysis Safety | PASS | Static analysis only; no execution, no new bounded-input paths beyond existing traversal. |
