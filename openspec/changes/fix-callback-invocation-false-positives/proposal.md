## Why

The `_handle_call` fallthrough in `analysis/detector.py` emits
`CallbackInvocation` with `confidence: ambiguous` for class constructor
calls defined in the same module, even though their names are available
from the AST.

Issue #18 reports a broader baseline of **729+ `CallbackInvocation` gaps**
across 326 test pairings. The safe same-file constructors addressed here
contribute to that noisy contract effect surface.

Only provably safe class constructor calls are not genuinely ambiguous.
The fix uses same-module AST declarations while leaving imports and other
unresolved names ambiguous.

Ref: [GitHub Issue #18](https://github.com/zero-dot-force/snake-eyes/issues/18)

## What Changes

Recognize class constructors declared in the same lexical module or
function scope without treating imports or a naming convention as proof
that an arbitrary callable is effect-free:

1. **Detect trivial same-module `ClassDef` names** — classes with no
   decorators, keywords, or executable body and either no bases or exactly
   the built-in `Exception`/`BaseException` base are known-safe constructors.
   Add them to the known-name set alongside
   `local_func_names`.

2. **Respect lexical shadowing** — parameters, imports, assignments,
   control-flow binders, duplicate definitions, and enclosing-function
   bindings take precedence over a same-named class and remain ambiguous.

Imported names and PascalCase names remain ambiguous until a future
effect-specific resolver can identify their observable behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- **M1: ClassDef-aware call resolution** — `_handle_call` recognizes
  class names defined in the same module, suppressing false positives
  for same-file constructors.

- **M2: Scope-aware class resolution** — parameter bindings take
  precedence over module-level class names and remain ambiguous.

### Removed Capabilities

None.

## Constitution Alignment

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Protocol Fidelity | PASS | No JSON-RPC schema changes. Only accuracy of emitted effects changes. Determinism preserved. |
| II. Detection Accuracy | PASS | Eliminates false positives (bugs per constitution). Preserves ambiguous fallthrough for genuinely unknown names. |
| III. Python-Native Analysis | PASS | Uses Python's `ast` module to collect definitions and binding constructs within their lexical scopes. No new dependencies. |
| IV. Testability | PASS | Regression scenarios cover safe and ambiguous resolution boundaries. Coverage gate maintained. |
| V. Analysis Safety | PASS | No code execution. Static name resolution uses linear AST traversal and set/dict lookups. |

## Impact

- **False positive reduction**: Eliminates false `CallbackInvocation`
  gaps for same-module and nested class constructors.
- **Preserved ambiguity**: Imported, convention-named, shadowed, and
  non-trivial class calls continue to trigger `CallbackInvocation` when
  their effects cannot be proven statically.
- **Existing tests**: Golden expectations for pass-only built-in exception
  subclasses (such as `MyError(Exception)`) become callback-free. New tests
  cover the resolution and ambiguity boundaries.
- **Protocol compliance**: No changes to JSON-RPC protocol or
  response schemas. Only the accuracy of emitted effects improves.
- **Downstream**: Gaze reports become cleaner — fewer ambiguous
  effects means more actionable contract surfaces.
