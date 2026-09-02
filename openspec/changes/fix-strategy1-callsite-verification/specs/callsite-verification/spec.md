## ADDED Requirements

### Requirement: Strategy-1 name-convention pairings SHALL verify call-site presence
After a name-convention match is found (test name prefix-strips to a target function name), the system SHALL verify that the test function body contains at least one direct call to the matched target function name. If no matching call is found, the pairing SHALL NOT be emitted.

#### Scenario: Name match with direct call present
- **WHEN** a test function `test_foo` has its prefix stripped to `foo`, and a target function named `foo` exists, and the test body contains a call to `foo()`
- **THEN** the pairing SHALL be emitted with the standard name-convention confidence (90 for exact match, 70 for case-only match)

#### Scenario: Name match with attribute call present
- **WHEN** a test function `test_foo` has its prefix stripped to `foo`, and a target function named `foo` exists, and the test body contains a call like `obj.foo()` (attribute call)
- **THEN** the pairing SHALL be emitted with the standard name-convention confidence

#### Scenario: Name match with no call present
- **WHEN** a test function `test_add` prefix-strips to `add`, and a target function `add` exists (exact match), but the test body does NOT contain any call to `add()`
- **THEN** the pairing SHALL NOT be emitted, allowing the test to fall through to strategy-2 and strategy-3

#### Scenario: Case-only name match with call present
- **WHEN** a test function `test_Add` prefix-strips to `Add`, and a target function `add` exists (case-only match), and the test body contains a call to `add()`
- **THEN** the pairing SHALL be emitted with confidence 70

#### Scenario: Case-only name match with no call present
- **WHEN** a test function `test_Add` prefix-strips to `Add`, and a target function `add` exists (case-only match), but the test body does NOT contain any call to `add()`
- **THEN** the pairing SHALL NOT be emitted, allowing the test to fall through to strategy-2 and strategy-3

#### Scenario: Fallthrough to later strategies after suppression
- **WHEN** a strategy-1 pairing is suppressed due to missing call-site, and the test body contains a direct call to a different target function
- **THEN** strategy-2 (direct-call) SHALL match that test to the actually-called target at confidence 80

### Requirement: Call-site extraction SHALL reuse existing `_direct_call_names` helper
The call-site verification in strategy-1 SHALL use the same `_direct_call_names` function used by strategy-2 to extract callee names from the test function AST. The system SHALL NOT introduce a duplicate AST walking implementation.

#### Scenario: Consistent call extraction between strategies
- **WHEN** strategy-1 verifies call-site presence for a test function
- **THEN** the set of detected callee names SHALL be identical to what strategy-2 would detect for the same test function

### Requirement: Strategy-1 verification SHALL only check direct calls
Call-site verification SHALL only check for direct calls within the test function body. Transitive calls (calls made by functions called by the test) SHALL NOT be considered by strategy-1. Transitive call resolution is the domain of strategy-3.

#### Scenario: Indirect call through helper
- **WHEN** a test function `test_foo` calls `helper()`, and `helper()` internally calls `foo()`, but `test_foo` does not directly call `foo()`
- **THEN** strategy-1 SHALL NOT emit a pairing for `test_foo` → `foo` (the test may be paired via strategy-3 instead)
