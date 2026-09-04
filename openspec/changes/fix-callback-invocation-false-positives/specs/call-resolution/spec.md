## Relationship to Prior Spec

This spec refines the "ambiguous constructs reported, never dropped"
requirement from the detector spec
([detector spec](../../../analysis-methods/specs/detector/spec.md)).
That requirement states that calls to names
not on the allowlist SHALL fall through to `CallbackInvocation` with
`confidence: ambiguous`. This spec expands the set of statically-
resolvable names by adding ClassDef name collection. The prior
requirement's intent — that genuinely ambiguous calls are never
silently dropped — is preserved. Only safe, unshadowed local ClassDef
names are resolved; imported and convention-named calls remain ambiguous
unless a separate effect-specific rule resolves them.

## Coverage Strategy

All tests are unit-level, exercising `_handle_call` through the
detector's `analyze_source` function with inline source strings.
Tests should assert the complete effect list (not just absence of
`CallbackInvocation`) to prevent false passes. No integration
(JSON-RPC) tests required since the change is internal to the
detector. The existing 85% coverage gate applies.

## ADDED Requirements

### Requirement: ClassDef-aware call resolution
The detector SHALL collect trivial `ast.ClassDef` names from the module
body and include them in the set of known callable names. A class is
trivial only when it has no keywords, decorators, or executable body and
has either no bases or exactly the built-in `Exception` or `BaseException`
base. When the called name matches such an unshadowed class defined in
the same module, the call SHALL NOT be reported as `CallbackInvocation`.

#### Scenario: Same-module class constructor
- **GIVEN** a trivial, unshadowed class defined directly in the module body
- **WHEN** a function calls `MyHelper(...)` and `class MyHelper: pass`
  is defined at module level in the same file
- **THEN** no `CallbackInvocation` effect is emitted for that call

#### Scenario: Nested class constructor
- **GIVEN** a trivial, unshadowed class defined directly in a function body
- **WHEN** a function defines `class Inner: pass` as a nested class
  and then calls `Inner(...)`
- **THEN** no `CallbackInvocation` effect is emitted for that call

#### Scenario: Parameter shadows module class
- **GIVEN** a trivial module class and a same-named function parameter
- **WHEN** a function parameter has the same name as a module-level
  class and is called
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL be
  emitted because the parameter is the runtime binding

#### Scenario: Rebound class name
- **GIVEN** a class name that would otherwise qualify for safe resolution
- **WHEN** a safe local class name is reassigned, imported, or captured by
  a pattern, loop, context manager, or exception handler in its lexical
  scope, or shadowed by an enclosing function binding
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL be
  emitted because the class binding is no longer proven

Binding analysis SHALL be conservative and scope-wide. A competing binding
anywhere in the lexical scope preserves ambiguity regardless of source order.
Wildcard imports, conditional class definitions, explicit global writes, and
mutation of a class's `__init__` or `__new__` attributes also preserve
ambiguity. Constructor mutation includes direct assignment or deletion and
statically identifiable `setattr`/`delattr` calls. Global declarations apply
throughout their function even when nested under control flow.

Direct-name aliases SHALL retain the constructor identity resolved when each
assignment executes. Constructor mutation through direct, transitive, or
class-body aliases SHALL preserve ambiguity. Later alias rebinding or deletion
SHALL affect only that alias and SHALL NOT retroactively change prior aliases.

#### Scenario: Constructor mutation through an alias chain
- **GIVEN** a safe class with one or more direct-name aliases
- **WHEN** `__init__` or `__new__` is mutated through an alias, including an
  alias retained in a class namespace
- **THEN** a call to the original class SHALL emit `CallbackInvocation` with
  `confidence: ambiguous`

#### Scenario: Shadowed exception base
- **GIVEN** a pass-only class with a syntactically supported exception base
- **WHEN** a pass-only class inherits from `Exception` or `BaseException`
  whose binding is not proven to be the built-in exception class
- **THEN** a call to that class SHALL emit `CallbackInvocation` with
  `confidence: ambiguous`

#### Scenario: Effectful class constructor
- **GIVEN** a same-module class that is not structurally trivial
- **WHEN** a function calls a same-module class with an `__init__`
  method or another executable class construct
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL be emitted

#### Scenario: Unknown non-PascalCase name from unresolved source
- **GIVEN** an unresolved callable name with no effect-specific rule
- **WHEN** a function calls `external_helper(...)` and
  `external_helper` is NOT defined in the same module, NOT in
  `import_aliases`, NOT in `_PURE_BUILTINS`, and does NOT match
  PascalCase
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL
  still be emitted

### Requirement: Ambiguous imported and convention-named calls
The detector SHALL emit `CallbackInvocation` with
`confidence: ambiguous` for imported and convention-named `ast.Name`
calls unless a separate effect-specific rule resolves their observable
behavior.

#### Scenario: Imported callable
- **GIVEN** an imported callable with no effect-specific rule
- **WHEN** a function calls an imported name such as `Path(...)`
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL be emitted

#### Scenario: PascalCase name not defined locally
- **GIVEN** a PascalCase callable name with no local definition
- **WHEN** a function calls `SomeClass(...)` that is not a local class
- **THEN** `CallbackInvocation` with `confidence: ambiguous` SHALL be emitted

### Requirement: Resolution order
After effect-specific call rules have not matched, `_handle_call` SHALL
apply the following unresolved-name fallback checks in order:

1. `_PURE_BUILTINS` set membership (existing, unchanged)
2. `local_func_names` set membership for directly resolved definitions
3. `module_func_names` membership, guarded by local, nonlocal, enclosing, and
   explicit-global binding semantics
4. Fallthrough: emit `CallbackInvocation` ambiguous

Each check SHALL short-circuit — if a name is resolved at any step,
subsequent checks SHALL NOT execute.
