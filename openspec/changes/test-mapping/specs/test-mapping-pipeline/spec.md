## ADDED Requirements

### Requirement: Orchestration entry point

The pipeline SHALL expose `run_test_mapping(root_path, patterns) -> list[dict]` that composes, in order: file discovery, target analysis (to obtain side effects on targets), test-function collection, pairing, assertion detection, effect-type inference, and serialization into protocol mapping dictionaries.

#### Scenario: Pipeline over the sample project yields mapping rows
- **WHEN** `run_test_mapping` runs over the `sample_project` fixture
- **THEN** it returns at least two mapping rows, each containing all required protocol keys

### Requirement: Test-function collection

The pipeline SHALL collect as test functions all `FunctionDef` and `AsyncFunctionDef` nodes whose names start with `test_`, plus methods whose names start with `test` that are defined on classes subclassing `unittest.TestCase`. A class is recognized as a `unittest.TestCase` subclass by a shallow match on its base names (`TestCase` or `unittest.TestCase`); transitively- or alias-derived subclasses are a documented known limitation (an acknowledged false negative).

#### Scenario: Pytest-style and unittest-style tests are both collected
- **WHEN** a test file contains a top-level `def test_add(): ...` and a `class T(unittest.TestCase)` with a `def test_x(self): ...` method
- **THEN** both `test_add` and `T.test_x` are collected as test functions

### Requirement: Pairing targets restricted to source files

The pipeline SHALL treat only production functions defined in `discover().source_files` as pairing targets; functions defined in test files SHALL NOT be pairing targets. Because `analyze_path` enumerates both source and test files, the pipeline SHALL filter analyzed `FunctionRecord`s to those whose `file` is a discovered source file before pairing.

#### Scenario: Test-module helper is never a target
- **WHEN** a test module defines a helper named `add` and a production module also defines `add`
- **THEN** tests pair only to the production `add`, and the test-module `add` is never emitted as a `target_function`

### Requirement: Bounded, guarded parsing of untrusted test files

The pipeline SHALL read test files through the shared guarded reader (`iter_source_files` / `is_analyzable_file`), which enforces the `MAX_FILE_BYTES` (16 MiB) byte cap; a test file exceeding the byte cap SHALL be skipped. The `MAX_AST_DEPTH` recursion budget is a visitor-level guard (not enforced by the reader), so the pipeline's own traversals SHALL enforce it: test-function collection SHALL reuse the depth-guarded `enumerate_functions_with_spans`, and the assertion walk SHALL be depth-guarded or SHALL catch `RecursionError`. An over-deep-but-parseable test file SHALL be skipped (yielding no rows) rather than aborting the request, and no untrusted input SHALL surface as an internal error (-32603).

#### Scenario: Oversized or over-deep test file is skipped
- **WHEN** a test file exceeds the byte cap or AST-depth budget
- **THEN** the pipeline skips that file and continues, producing rows for the remaining files without raising an internal error

### Requirement: Static-analysis-only execution

The pipeline SHALL perform static analysis only: it SHALL NOT execute analyzed code, SHALL NOT run pytest, and SHALL NOT read coverage data.

#### Scenario: No execution or coverage access during mapping
- **WHEN** `run_test_mapping` processes a project
- **THEN** it parses source statically and never invokes pytest, never imports/executes analyzed modules, and never reads `.coverage`/coverage.json

### Requirement: Deterministic ordering

The pipeline SHALL order `mappings` by a stable composite key `(test_file, test_function, assertion_line, assertion_col, target_package, target_function)`, where `assertion_line` is the integer source line of the assertion compared numerically (so line 2 sorts before line 10, which a `path:line` string would not) and `assertion_col` is the integer column offset (or an equivalent stable collection index) that breaks ties when several assertions share one source line, making the key a total order. Output SHALL be byte-identical across repeated runs on the same input, including across separate processes launched with different `PYTHONHASHSEED` values.

#### Scenario: Repeated runs are byte-identical
- **WHEN** `run_test_mapping` is executed twice on the same unchanged project
- **THEN** the two serialized results are byte-identical

#### Scenario: Output is stable across hash seeds
- **WHEN** the server serializes `test_mapping` output in two separate processes launched with `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1` over the same project
- **THEN** the two serialized results are byte-identical

#### Scenario: Rows appear in numeric-line order on a fixture
- **WHEN** `run_test_mapping` runs over a fixture whose assertions span single- and double-digit lines (e.g. lines 2 and 10)
- **THEN** the rows appear in ascending order of the composite key with the line compared numerically, asserted against the expected concrete ordering (not only byte-equality)

### Requirement: Single-valued return contract

`run_test_mapping` SHALL return a `list[dict]` (an empty list when there are no mappings). Wrapping the list into the `{"mappings": [...]}` response envelope SHALL be performed only by the server handler, not by the pipeline.

#### Scenario: Pipeline returns a bare list
- **WHEN** `run_test_mapping` completes
- **THEN** it returns a `list[dict]` and does not itself wrap the result in a `{"mappings": ...}` object

#### Scenario: Empty project returns an empty list
- **WHEN** `run_test_mapping` runs over a project with no pairable tests
- **THEN** it returns `[]`
