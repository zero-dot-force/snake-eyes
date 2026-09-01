## ADDED Requirements

### Requirement: Name-convention pairing (Priority 1)

The pairing engine SHALL pair a test function to a production function by name convention, stripping a leading `test_`/`Test` (or `test`/`Test` camel prefix) from the test name and matching the remainder to a production function name. An exact-name match SHALL yield confidence 90; a match that differs only by letter case SHALL yield confidence 70.

#### Scenario: Exact name match
- **WHEN** a test named `test_add` is evaluated against a production function `add`
- **THEN** they are paired with `confidence` 90

#### Scenario: Case-only match
- **WHEN** a test named `test_Add` is evaluated against a production function `add` and no exact-case match exists
- **THEN** they are paired with `confidence` 70

### Requirement: Direct-call pairing (Priority 2)

When name convention does not pair a test, the engine SHALL pair the test to a production function whose name appears as a direct `Call` in the test function's AST, yielding confidence 80.

#### Scenario: Test directly calls the target
- **WHEN** a test named `test_it_works` contains a call to `divide` and does not name-match any production function
- **THEN** it is paired to `divide` with `confidence` 80

### Requirement: Transitive-call pairing (Priority 3)

When neither name convention nor direct call pairs a test, the engine SHALL attempt to pair via an astroid transitive call graph using breadth-first search with a depth limit of 5, yielding confidence 75. The transitive call graph SHALL be built once per `test_mapping` request and reused for every unpaired-test lookup (mirroring `build_caller_index`/`CallerIndex.count` in `analysis/inference.py`), never rebuilt per test. Callees SHALL be matched by their resolved defining file path (not by a `derive_package` dotted name, which under a `src/` layout would not equal astroid's inferred module name). To preserve per-request isolation and bound memory in the long-lived stdio server, the engine SHALL clear `astroid.MANAGER` before building the graph and again in a `finally` block, mirroring `analysis/inference.py`. This strategy SHALL degrade gracefully: it SHALL catch the broadened exception set (astroid errors, `RecursionError`, `MemoryError`, and an unexpected-error catch-all) and, on any such error, skip strategy 3 while still returning results from strategies 1 and 2 — no strategy-3 failure SHALL surface as an internal error (-32603). Each skip or degrade SHALL emit a one-line diagnostic to stderr (stdout is reserved for JSON-RPC), mirroring `analysis/inference.py`. The broadened catch SHALL NOT absorb `FileNotFoundError`, which propagates so a non-existent root is reported as -32602 by discovery, not by the strategy-3 catch.

#### Scenario: Transitive call within depth limit
- **WHEN** a test calls a helper that (within 5 hops) calls the target production function, and no earlier strategy matched
- **THEN** the test is paired to the target with `confidence` 75

#### Scenario: Target beyond the depth limit is not paired by strategy 3
- **WHEN** the target production function is reachable from the test only through a call chain longer than 5 hops
- **THEN** strategy 3 does not pair the test to that target

#### Scenario: Astroid unavailable degrades without failing
- **WHEN** astroid cannot import or parse the analyzed project during strategy 3
- **THEN** strategy 3 is skipped and any pairs found by strategies 1 and 2 are still returned

#### Scenario: Astroid cache is isolated per request
- **WHEN** strategy 3 runs across two `test_mapping` requests over different project trees within the same long-lived process
- **THEN** the astroid manager cache is cleared before building each request's graph and released afterward, so inference from one tree cannot contaminate the other

#### Scenario: Pathological input degrades without an internal error
- **WHEN** strategy 3 raises a `RecursionError`, `MemoryError`, or any unexpected error on pathological-but-parseable input
- **THEN** the strategy is skipped, strategies 1 and 2 results are returned, and no internal error (-32603) surfaces

### Requirement: First-match-wins and de-duplication

The engine SHALL evaluate strategies in priority order and stop at the first strategy that pairs a given test, and SHALL NOT emit duplicate pairs for the same `(test_function, test_file, target_package, target_function)` key. When a single strategy matches several same-named production functions across different packages, the engine SHALL pair each distinct `(target_package, target_function)` deterministically in `analyze_path` order (sorted by `(file, line, name)`). Unpaired tests SHALL produce no mapping rows (no confidence-0 rows).

#### Scenario: Highest-priority strategy wins
- **WHEN** a test both name-matches and directly calls the same target
- **THEN** a single pair is produced using the name-convention confidence (90), not a duplicate

#### Scenario: Unpaired test produces no rows
- **WHEN** a test neither name-matches nor calls (directly or transitively) any production function
- **THEN** no mapping row is emitted for that test

#### Scenario: Same-named targets in different packages are disambiguated
- **WHEN** a test name-matches a function `add` that is defined in two different packages
- **THEN** a distinct mapping row is emitted for each `(target_package, target_function)`, ordered deterministically in `analyze_path` order

### Requirement: Target package derivation

The engine SHALL derive `target_package` from the production file's dotted module path using the shared `derive_package` helper (the same helper used by the `analyze` method); equivalently, it MAY read `FunctionRecord.package`, which already carries the same `derive_package` value from analysis.

#### Scenario: Package derived from module path
- **WHEN** a target function is defined in `src/sample/calculator.py`
- **THEN** `target_package` is the dotted module path produced by `derive_package` for that file
