## Relationship to Prior Spec

This delta modifies the `test-mapping-method` capability spec
([test-mapping-method spec](../../../test-mapping/specs/test-mapping-method/spec.md)).
The prior spec defined the `test_mapping` result envelope as an object
whose sole top-level key is `mappings`. This delta adds a second top-level
key, `assertion_detection_confidence`, carrying the analyzer-computed
assertion-detection confidence so Gaze's external-analyzer adapter can
surface a non-zero value. The `mappings` array and every mapping-row field
are unchanged; only the response envelope gains a field.

## Coverage Strategy

Server-level conformance tests in `tests/test_test_mapping_method.py` SHALL
assert that a successful `test_mapping` response contains exactly the two
top-level keys `mappings` (list) and `assertion_detection_confidence`
(int in 0–100), and that the value matches the confidence computed for
the fixture. The existing determinism and error-mapping tests remain and
are updated for the new envelope shape. The 85% coverage gate applies.

## MODIFIED Requirements

### Requirement: test_mapping JSON-RPC method

The server SHALL expose a `test_mapping` JSON-RPC method that accepts a params object of the form `{"root_path": <absolute string>, "patterns": <list of strings>}` and returns a result object of the form `{"mappings": [...], "assertion_detection_confidence": <int>}`. The `mappings` array SHALL conform to Gaze analyzer protocol v1.1.0; `assertion_detection_confidence` is a forward-compatible extension (additive — older Gaze versions ignore the unknown key during JSON decoding). The method SHALL be registered in the server dispatch table under the key `"test_mapping"`.

#### Scenario: Valid request returns a mappings envelope
- **WHEN** a `test_mapping` request is dispatched with a valid `root_path` and `patterns`
- **THEN** the result is an object whose top-level keys are exactly `mappings` (a JSON array) and `assertion_detection_confidence` (an integer in 0–100)

#### Scenario: Project with no tests returns empty mappings
- **WHEN** a `test_mapping` request targets a root that contains no test files
- **THEN** the result is `{"mappings": [], "assertion_detection_confidence": 0}` returned as a success result, not a JSON-RPC error

#### Scenario: Project with no test/target pairs returns empty mappings
- **WHEN** test files exist but none can be paired to a production function
- **THEN** the result contains an empty `mappings` array and an `assertion_detection_confidence` integer in 0–100 reflecting assertion detection across the collected test functions, returned as a success result, not a JSON-RPC error

## ADDED Requirements

### Requirement: assertion_detection_confidence field contract

The `assertion_detection_confidence` field SHALL be present in every successful `test_mapping` result and SHALL be an integer in the inclusive range 0–100. It SHALL be computed by the analyzer as the rounded percentage of collected test functions in which at least one assertion was detected, using integer arithmetic `(100 * detected + total // 2) // total` when `total` (the number of collected test functions) is greater than zero, and SHALL be `0` when `total` is zero.

#### Scenario: Confidence reflects detected assertions
- **WHEN** a `test_mapping` request is dispatched over a project whose collected test functions each contain at least one detected assertion
- **THEN** `assertion_detection_confidence` equals 100

#### Scenario: Confidence rounds half up for a partial detection
- **WHEN** a `test_mapping` request is dispatched over a project in which some but not all collected test functions contain a detected assertion
- **THEN** `assertion_detection_confidence` equals the round-half-up percentage `(100 * detected + total // 2) // total` of the collected test functions (e.g. 1 of 3 → 33, 2 of 3 → 67)

#### Scenario: Confidence is zero when no assertions detected
- **WHEN** a `test_mapping` request is dispatched over a project whose collected test functions contain no detected assertions
- **THEN** `assertion_detection_confidence` equals 0

#### Scenario: Confidence is zero when no test functions collected
- **WHEN** a `test_mapping` request is dispatched over a project with no collected test functions
- **THEN** `assertion_detection_confidence` equals 0

#### Scenario: Confidence value is a plain integer
- **WHEN** a `test_mapping` response is serialized
- **THEN** `assertion_detection_confidence` serializes as a JSON number with no fractional component, and its type is `int`
