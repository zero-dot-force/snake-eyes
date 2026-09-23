## Relationship to Prior Spec

This delta modifies the `test-mapping-pipeline` capability spec
([test-mapping-pipeline spec](../../../test-mapping/specs/test-mapping-pipeline/spec.md)).
The prior spec defined `run_test_mapping` as returning a bare `list[dict]`
of mapping rows, with assertion collection performed only inside the
pairing loop. This delta changes the pipeline to (a) collect assertions
for every collected test function — paired or not — and (b) return both
the mapping rows and a computed assertion-detection confidence, so the
server handler can emit the extended envelope. The `assertion-detection`
capability's per-paired-test collection wording is not modified here:
mapping-row output is unchanged (unpaired tests still emit no rows);
assertion collection broadens to every collected test function for
confidence computation only.

## Coverage Strategy

Pipeline unit tests exercise `run_test_mapping` (and any extracted
confidence helper) against inline source strings and the
`sample_project` fixture, asserting the returned confidence for cases
with all-asserted, partially-asserted, and no-assertion test functions,
and for projects with test functions but no production targets. The
existing determinism (byte-identical, hash-seed-stable) tests remain and
are updated for the new return shape. The 85% coverage gate applies.

## MODIFIED Requirements

### Requirement: Orchestration entry point

The pipeline SHALL expose `run_test_mapping(root_path, patterns)` that composes, in order: file discovery, target analysis (to obtain side effects on targets), test-function collection, assertion detection over every collected test function, pairing, effect-type inference, confidence computation, and serialization into protocol mapping dictionaries. The return value SHALL carry both the list of mapping rows and the computed assertion-detection confidence.

#### Scenario: Pipeline over the sample project yields mapping rows and a confidence
- **WHEN** `run_test_mapping` runs over the `sample_project` fixture
- **THEN** it returns a result whose mappings contain at least two mapping rows (each containing all required protocol keys) and whose assertion-detection confidence is an integer in 0–100

### Requirement: Single-valued return contract

`run_test_mapping` SHALL return a single result object exposing `mappings: list[dict[str, Any]]` (an empty list when there are no mappings) and `assertion_detection_confidence: int`. Wrapping the result into the `{"mappings": [...], "assertion_detection_confidence": <int>}` response envelope SHALL be performed only by the server handler, not by the pipeline.

#### Scenario: Pipeline returns a result object
- **WHEN** `run_test_mapping` completes
- **THEN** it returns a single result object carrying both `mappings` and `assertion_detection_confidence`, and does not itself wrap the result in a `{"mappings": ...}` object

#### Scenario: Empty project returns an empty list and zero confidence
- **WHEN** `run_test_mapping` runs over a project with no pairable tests and no collected test functions
- **THEN** it returns a result whose `mappings` is `[]` and whose `assertion_detection_confidence` is `0`

## ADDED Requirements

### Requirement: Assertion detection confidence computation

The pipeline SHALL collect assertions for every collected test function — regardless of whether that function is paired to a production target — and SHALL compute `assertion_detection_confidence` as the rounded percentage of collected test functions in which at least one assertion was detected. When at least one test function is collected, the confidence SHALL equal `(100 * detected + total // 2) // total` (integer arithmetic, round half up), where `detected` is the number of collected test functions with at least one detected assertion and `total` is the total number of collected test functions. When no test functions are collected, the confidence SHALL be `0`. A test function whose assertion collection is interrupted by a guarded parse exception (e.g. `RecursionError`, which `collect_assertions` handles internally and returns partial results for) SHALL be counted as detected if and only if at least one assertion was collected before the interruption, and the request SHALL complete without an internal error.

#### Scenario: Confidence counted across unpaired tests
- **WHEN** a project contains test functions that are not paired to any production target
- **THEN** those test functions still contribute to the assertion-detection confidence based on their own detected assertions

#### Scenario: Confidence computed before pairing short-circuits
- **WHEN** a project has collected test functions but no production targets
- **THEN** `run_test_mapping` returns a result with empty `mappings` and a confidence derived from the collected test functions' assertions, rather than an early `[]`

#### Scenario: Empty pairing inputs produce no error
- **WHEN** `run_test_mapping` runs over a project with test functions but no production targets, or with no test functions
- **THEN** pairing yields zero rows without an internal error and the result's `mappings` is `[]`

#### Scenario: Confidence is a rounded integer for partial detection
- **WHEN** a project collects test functions where only some contain a detected assertion
- **THEN** `assertion_detection_confidence` equals `(100 * detected + total // 2) // total` (e.g. 1 of 3 → 33, 2 of 3 → 67)

#### Scenario: Confidence is a stable integer across runs
- **WHEN** `run_test_mapping` is executed twice on the same unchanged project
- **THEN** both results report the same `assertion_detection_confidence` integer, and the serialized outputs are byte-identical

#### Scenario: Degenerate assertion walk does not corrupt confidence
- **WHEN** a collected test function's assertion walk is interrupted by `RecursionError` or another guarded parse exception
- **THEN** that function is counted as detected if and only if at least one assertion was collected before the interruption (a function whose walk aborted before collecting any assertion is counted as not detected), and the request completes without an internal error
