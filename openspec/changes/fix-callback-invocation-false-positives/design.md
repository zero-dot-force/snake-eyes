## Context

The `ast.Name` fallthrough in `_handle_call`
is the final fallthrough for `ast.Name` calls. It checks two
allowlists — `_PURE_BUILTINS` (stdlib builtins) and
`local_func_names` (module-level + nested function defs) — and emits
`CallbackInvocation` with `confidence: ambiguous` for anything not
matched.

Constraints:
- The detector spec requires "ambiguous constructs reported, never
  dropped." Only pass-only classes with no bases, or exactly the built-in
  `Exception`/`BaseException` base, with all relevant bindings proven
  unshadowed, can be treated as safe here; other class construction
  remains ambiguous.
- Constitution principle 2 (Detection Accuracy): false positives are
  bugs, just like false negatives.

## Goals / Non-Goals

**Goals:**
- Eliminate false `CallbackInvocation` for provably safe same-module class
  constructors by collecting `ClassDef` names alongside
  `module_func_names`
- Maintain detection of genuinely ambiguous callbacks, including
  imports and PascalCase names whose effects cannot be proven

**Non-Goals:**
- Analyzing the imported module's source to determine if the
  callable has side effects (that's Gaze's job across analyzers)
- Handling `ast.Attribute` call resolution (e.g., `module.Class()`)
  — that's a separate code path already handled
- Eliminating ALL false positives (some edge cases like `exec()`
  return values being called are legitimately ambiguous)
- Adding astroid-based type inference to the call resolution (too
  expensive for the hot path)

## Decisions

### D1: Scope-aware local class resolution

**Decision**: Apply three checks in sequence before falling through
to `CallbackInvocation`:

1. `_PURE_BUILTINS` (existing) — no change
2. `local_func_names` (existing) — expand to include safe nested `ClassDef` names
3. `module_func_names` — resolve safe module definitions,
   except where a parameter, local, nonlocal, module-level, or enclosing
   function binding shadows that name

**Rationale**: A safe local ClassDef is structurally visible to the parser,
while imports, naming conventions, rebinding, and non-trivial classes do
not prove that a call is pure. The binding guards follow Python lexical
binding rules at the module and function scopes. They are intentionally
scope-wide rather than source-order-sensitive, so any competing binding in
the scope preserves ambiguity even when it appears after the call.

**Alternatives considered**:
- *Import and PascalCase suppression*: Rejected because neither proves
  a callable is effect-free and either can silently drop real effects.
- *Astroid type inference*: Too expensive for the hot path and
  already used in `inference.py` for a different purpose
  (caller-count signals, not effect detection). Rejected.

### D2: Expand `local_func_names` to include `ClassDef` names

**Decision**: Use one scope-aware AST visitor to collect all binding forms
within a module or function without descending into child lexical scopes.
In `_analyze_tree`, collect safe `ClassDef` names into the same
`module_func_names` set (see D4 — rename deferred). In `_analyze_func_node`,
also collect nested safe `ClassDef` names into `local_func_names`, and carry
enclosing-function bindings into nested-function analysis.

**Rationale**: Safe local class constructors are statically-resolvable
callables, same as function defs. The existing `local_func_names`
mechanism is the right place; module and local binding sets prevent
rebinding from being incorrectly resolved. Binding counts also reject
duplicate or competing definitions. Wildcard imports, global writes, and
constructor attribute mutations, including direct assignment and static
`setattr`/`delattr` calls in functions, lambdas, and class bodies, invalidate
the class in the lexical scope where the target resolves. Global declarations
are collected across their complete function scope, including control-flow
blocks. Shared module sets, composite membership views, and persistent
closure-binding chains avoid per-function cumulative copies.
Direct-name aliases are canonicalized when assigned, so transitive and
class-body aliases retain source-ordered object identity in constant-time
mutation lookups. Rebinding or deleting an alias updates only that alias.

**Alternatives considered**:
- *Separate `module_class_names` set*: Adds a new parameter
  threaded through the entire call chain. More precise naming but
  higher coupling cost for no behavioral difference. Rejected.

### D4: No parameter rename in this change

**Decision**: Keep the parameter name `local_func_names` and the
variable name `module_func_names` even though they now include class
names. Add a comment noting the expanded scope.

**Rationale**: Renaming threads through 16+ call sites across the
module. The rename is mechanical but noisy — better as a separate
cleanup if desired. The functional change is more important.

**Alternatives considered**:
- *Rename to `local_callable_names`*: Correct but adds diff noise.
  Can be done as follow-up. Deferred.

## Risks / Trade-offs

- **[Risk] Imported and PascalCase constructor false positives remain**:
  their observable behavior cannot be proven with this local AST pass.
  → **Mitigation**: retain `CallbackInvocation` with ambiguous
  confidence until an effect-specific resolver is introduced.
