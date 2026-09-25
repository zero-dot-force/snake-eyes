## ADDED Requirements

### Requirement: `compute_complexity` `.extend()` is explicitly asserted
The test suite SHALL include a container-state observation that verifies the returned entries list grew by the expected number of elements and contains expected elements, so the `.extend()` effect at `src/snake_eyes/analysis/complexity.py:159` can be mapped by the analyzer.

#### Scenario: Length and membership assertion covers `.extend()`
- **WHEN** a test calls `compute_complexity` with a deterministic source tree
- **THEN** the test asserts `len(entries)` equals the expected count
- **AND** the test asserts expected function names are present in the entries

### Requirement: `compute_complexity` `.sort()` is explicitly asserted
The test suite SHALL include a container-state observation that verifies the returned entries list is ordered by `(file, line, name)`, so the `.sort()` effect at `src/snake_eyes/analysis/complexity.py:161` can be mapped by the analyzer.

#### Scenario: Ordering assertion covers `.sort()`
- **WHEN** a test calls `compute_complexity` with a deterministic source tree containing multiple files
- **THEN** the test asserts the ordered projection of entries matches the documented `(file, line, name)` order

### Requirement: `parse_coverage` `.sort()` is explicitly asserted
The test suite SHALL include a container-state observation that verifies the returned coverage entries are ordered by `(file, start_line, function)`, so the `.sort()` effect at `src/snake_eyes/coverage.py:359` can be mapped in the canonical value test.

#### Scenario: Ordering assertion covers `.sort()` in value test
- **WHEN** a test calls `parse_coverage` with a deterministic coverage payload
- **THEN** the test asserts the ordered projection of entries matches the documented `(file, start_line, function)` order

### Requirement: Existing `.append()` coverage is preserved
The test suite SHALL continue to map the `.append()` effect in `function_record_to_dict` through serialization assertions on the returned `side_effects` list.

#### Scenario: Serialization assertions continue to cover `.append()`
- **WHEN** a test calls `function_record_to_dict` with a record containing side effects
- **THEN** the test asserts the shape and content of `result["side_effects"]`

### Requirement: Quality report regression verification
The implementation SHALL capture a workspace-local `gaze quality` report before and after the test changes and compare unique `(effect_type, source_file, source_line)` identities to confirm the targeted `ContainerMutation` gaps close in at least one focused test per target function.

#### Scenario: Before/after identity comparison
- **WHEN** the targeted `ContainerMutation` identities from the before and after reports are compared
- **THEN** `se-65715d40` (`complexity.py:161`) and `se-48443a2b` (`coverage.py:359`) are no longer listed as gaps in the focused tests
- **AND** no new unique gaps appear for unchanged targets
