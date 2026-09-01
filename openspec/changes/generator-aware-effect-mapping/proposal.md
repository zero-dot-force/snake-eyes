# Proposal: Generator-Aware Effect Mapping

## Why

`infer_side_effect_type` in `quality/mapping.py` uses a fallback chain for value-type assertions (equality, comparison, identity, membership) that terminates at `ReturnValue`. For generator functions, the detected side effect is `GeneratorYield` (P1 tier), not `ReturnValue` (P0 tier). Since `GeneratorYield` is P1 and the chain only searches P0 effects before falling back to `ReturnValue`, generator functions never get matched.

This causes gaze's `findSideEffectID` to find no corresponding effect for the mapped `ReturnValue` type, sending all assertions for generator functions to `UnmappedAssertions` with 0% contract coverage. The bug is observable with any generator function (e.g., `iter_source_files` in `discovery.py` which yields file paths but whose test assertions map to `ReturnValue` instead of `GeneratorYield`).

References: GitHub issue #13. Depends on #6 (test-mapping) which introduces `quality/mapping.py`.

## What Changes

Extend the value-type assertion fallback chain in `infer_side_effect_type` to consider `GeneratorYield` (and `AsyncGeneratorYield`) before falling back to `ReturnValue`. The current chain is:

```
ReturnValue (if present) → first P0 effect → ReturnValue (fallback)
```

The fixed chain becomes:

```
ReturnValue (if present) → first P0 effect → GeneratorYield/AsyncGeneratorYield (if present) → ReturnValue (fallback)
```

The `generic` assertion-type chain was initially suspected of having the same gap, but analysis confirmed it already handles generators correctly — it returns the first detected effect regardless of tier, so `GeneratorYield` is returned when present. No code change is needed for the generic chain; a regression guard test confirms this behavior.

The existing spec (`effect-type-mapping/spec.md`) is updated to reflect the corrected requirement.

## Capabilities

### Modified

- **Value-type assertion mapping**: The fallback chain for equality, comparison, identity, and membership assertion types now checks for `GeneratorYield` and `AsyncGeneratorYield` effects before falling back to `ReturnValue`. Generator functions with value-type test assertions now correctly map to their yield effect type.
- **Generic assertion mapping**: Verified unchanged — the generic fallback chain already returns the first detected effect regardless of tier, so `GeneratorYield` is returned when present. A regression guard test confirms this existing behavior.

## Impact

- **Scope**: Single function (`infer_side_effect_type`) in `quality/mapping.py`, plus spec update
- **Risk**: LOW -- additive change to existing fallback chain; no behavioral change for non-generator functions
- **Testing**: New test cases for generator and async-generator scenarios; existing tests unchanged
- **Protocol**: No JSON-RPC protocol changes; this is an internal mapping accuracy fix
- **Constitution**: Aligns with Principle 2 (Detection Accuracy) -- false negatives (unmapped assertions for generators) are bugs
