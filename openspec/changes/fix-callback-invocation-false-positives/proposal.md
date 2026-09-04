## Why

The `_handle_call` fallthrough in `analysis/detector.py` emits
`CallbackInvocation` with `confidence: ambiguous` for any `ast.Name`
call that isn't in `_PURE_BUILTINS` or `local_func_names`. This
catches imported class constructors like `SignalResult(...)`,
`Path(...)`, and `DiscoveryResult(...)` — none of which are callbacks.

The result: **729+ false `CallbackInvocation` gaps** across 326 test
pairings. These inflate the contract effect surface, making Gaze
reports noisy and reducing trust in side-effect detection.

Class constructor calls are **not genuinely ambiguous** — they are
deterministic object instantiations. The detector already tracks
`import_aliases` (passed to `_EffectVisitor`) but never consults them
during the `_handle_call` fallthrough. The fix is to use information
the detector already has.

Ref: [GitHub Issue #18](https://github.com/zero-dot-force/snake-eyes/issues/18)

## What Changes

Expand the set of names recognized as "known safe" in `_handle_call`
so that class constructors and imported callables are not
misclassified as `CallbackInvocation`:

1. **Consult `import_aliases`** — names present in the module's
   import table are known symbols, not opaque callbacks. When a
   called name resolves to an import, skip the `CallbackInvocation`
   fallthrough.

2. **Detect same-module `ClassDef` names** — classes defined in the
   same file are known constructors. Add them to the known-name set
   alongside `local_func_names`.

3. **PascalCase naming convention heuristic** — as a secondary
   signal, names matching PascalCase (`^[A-Z][a-zA-Z0-9]*$`) are
   overwhelmingly class constructors in Python. Use this as an
   additional constructor hint when the name is not otherwise
   resolved.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- **M1: Import-aware call resolution** — `_handle_call` consults
  `import_aliases` before falling through to `CallbackInvocation`,
  suppressing false positives for imported names.

- **M2: ClassDef-aware call resolution** — `_handle_call` recognizes
  class names defined in the same module, suppressing false positives
  for same-file constructors.

- **M3: PascalCase constructor heuristic** — `_handle_call` uses
  naming convention as a secondary signal to identify likely
  constructors when no other resolution applies.

### Removed Capabilities

None.

## Constitution Alignment

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Protocol Fidelity | PASS | No JSON-RPC schema changes. Only accuracy of emitted effects changes. Determinism preserved. |
| II. Detection Accuracy | PASS | Eliminates false positives (bugs per constitution). Preserves ambiguous fallthrough for genuinely unknown names. |
| III. Python-Native Analysis | PASS | Uses `ast` module (`ClassDef`, `Name`) and existing `import_aliases`. No new dependencies. |
| IV. Testability | PASS | 7 test scenarios covering all resolution layers plus regression guards. Coverage gate maintained. |
| V. Analysis Safety | PASS | No code execution. Static name resolution only (set/dict lookups, regex match). |

## Impact

- **False positive reduction**: Eliminates the majority of 729+
  spurious `CallbackInvocation` gaps.
- **No false negative risk**: Genuine callbacks (lowercase names not
  in imports or class defs) still trigger `CallbackInvocation` as
  before.
- **Existing tests**: Existing golden tests that assert
  `CallbackInvocation` for PascalCase class names (e.g., `MyError`)
  will need updating — the behavioral change is intentional. New
  tests required for the three resolution strategies.
- **Protocol compliance**: No changes to JSON-RPC protocol or
  response schemas. Only the accuracy of emitted effects improves.
- **Downstream**: Gaze reports become cleaner — fewer ambiguous
  effects means more actionable contract surfaces.
