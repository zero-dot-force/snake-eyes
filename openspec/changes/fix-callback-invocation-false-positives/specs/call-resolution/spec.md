## Relationship to Prior Spec

This spec refines the "ambiguous constructs reported, never dropped"
requirement from the detector spec (`openspec/changes/analysis-methods/
specs/detector/spec.md`). That requirement states that calls to names
not on the allowlist SHALL fall through to `CallbackInvocation` with
`confidence: ambiguous`. This spec expands the set of statically-
resolvable names by adding import-alias resolution, ClassDef name
collection, and a PascalCase naming convention heuristic. The prior
requirement's intent — that genuinely ambiguous calls are never
silently dropped — is preserved. Names resolvable through imports,
ClassDef, or PascalCase convention are not genuinely ambiguous and
therefore do not fall under the "never dropped" mandate.

## Coverage Strategy

All tests are unit-level, exercising `_handle_call` through the
detector's `analyze_source` function with inline source strings.
Tests should assert the complete effect list (not just absence of
`CallbackInvocation`) to prevent false passes. No integration
(JSON-RPC) tests required since the change is internal to the
detector. The existing 85% coverage gate applies.

## ADDED Requirements

### Requirement: Import-aware call resolution
The `_handle_call` method SHALL check `self.import_aliases` before
emitting `CallbackInvocation` for an `ast.Name` call. When the called
name is present as a key in `import_aliases`, the call SHALL NOT be
reported as `CallbackInvocation`.

#### Scenario: Imported class constructor
- **WHEN** a function calls `SignalResult(...)` and `SignalResult` is
  in `import_aliases` (from `from .models import SignalResult`)
- **THEN** no `CallbackInvocation` effect is emitted for that call

#### Scenario: Imported function call
- **WHEN** a function calls `namedtuple(...)` and `namedtuple` is
  in `import_aliases` (from `from collections import namedtuple`)
- **THEN** no `CallbackInvocation` effect is emitted for that call

#### Scenario: Aliased import
- **WHEN** a function calls `np(...)` and `np` is in `import_aliases`
  (from `import numpy as np`)
- **THEN** no `CallbackInvocation` effect is emitted for that call

#### Scenario: Unknown name not in imports
- **WHEN** a function calls `callback(...)` and `callback` is NOT in
  `import_aliases`, NOT in `local_func_names`, and NOT in
  `_PURE_BUILTINS`
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL
  still be emitted

### Requirement: ClassDef-aware call resolution
The detector SHALL collect `ast.ClassDef` names from the module body
and include them in the set of known callable names. When the called
name matches a class defined in the same module, the call SHALL NOT
be reported as `CallbackInvocation`.

#### Scenario: Same-module class constructor
- **WHEN** a function calls `MyHelper(...)` and `class MyHelper` is
  defined at module level in the same file
- **THEN** no `CallbackInvocation` effect is emitted for that call

#### Scenario: Nested class constructor
- **WHEN** a function defines `class Inner: ...` as a nested class
  and then calls `Inner(...)`
- **THEN** no `CallbackInvocation` effect is emitted for that call

#### Scenario: Unknown non-PascalCase name from unresolved source
- **WHEN** a function calls `external_helper(...)` and
  `external_helper` is NOT defined in the same module, NOT in
  `import_aliases`, NOT in `_PURE_BUILTINS`, and does NOT match
  PascalCase
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL
  still be emitted

### Requirement: PascalCase constructor heuristic
The `_handle_call` method SHALL apply a PascalCase naming convention
check as a final resolution step before emitting `CallbackInvocation`.
Names matching the pattern `^[A-Z][a-zA-Z0-9]*$` SHALL be treated as
likely constructors and SHALL NOT trigger `CallbackInvocation`.

#### Scenario: PascalCase name not in imports or class defs
- **WHEN** a function calls `SomeClass(...)` and `SomeClass` is NOT
  in `import_aliases`, NOT in `local_func_names`, NOT in
  `_PURE_BUILTINS`, but matches PascalCase pattern
- **THEN** no `CallbackInvocation` effect is emitted for that call

#### Scenario: Lowercase name not resolved
- **WHEN** a function calls `unknown_func(...)` and the name does
  NOT match PascalCase, is NOT in any known-name set
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL
  be emitted

#### Scenario: ALL_CAPS name not matching PascalCase
- **WHEN** a function calls `SOME_CONSTANT(...)` and the name does
  NOT match `^[A-Z][a-zA-Z0-9]*$` (contains underscore)
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL
  be emitted (ALL_CAPS names are typically constants, not constructors)

### Requirement: Resolution order
The `_handle_call` method SHALL apply resolution checks in the
following order for `ast.Name` calls:

1. `_PURE_BUILTINS` set membership (existing, unchanged)
2. `local_func_names` set membership (expanded to include ClassDef)
3. `import_aliases` dict membership (new)
4. PascalCase pattern match (new)
5. Fallthrough: emit `CallbackInvocation` ambiguous

Each check SHALL short-circuit — if a name is resolved at any step,
subsequent checks SHALL NOT execute.

#### Scenario: Name in both PURE_BUILTINS and import_aliases
- **WHEN** a function calls `int(...)` which is in both
  `_PURE_BUILTINS` and `import_aliases`
- **THEN** resolution occurs at step 1 (`_PURE_BUILTINS`) and no
  `CallbackInvocation` is emitted

#### Scenario: Name in import_aliases but not local_func_names
- **WHEN** a function calls `Path(...)` which is in `import_aliases`
  but not in `local_func_names`
- **THEN** resolution occurs at step 3 (`import_aliases`) and no
  `CallbackInvocation` is emitted
