# Design: Generator-Aware Effect Mapping

## Context

`infer_side_effect_type` in `quality/mapping.py` maps assertion types to side-effect types using the target function's detected effects. The value-type assertion chain (equality, comparison, identity, membership) searches for `ReturnValue` first, then falls through P0-tier effects, and finally falls back to `ReturnValue`. The generic chain returns the first detected effect or `ReturnValue`.

Generator functions produce `GeneratorYield` (P1 tier) and async generators produce `AsyncGeneratorYield` (P2 tier). Neither is `ReturnValue`, and neither is P0-tier. The current chain skips both entirely, mapping to `ReturnValue` — a type that doesn't exist in the target's effect list. This causes gaze's `findSideEffectID` lookup to fail, sending all assertions to `UnmappedAssertions`.

The existing spec (`effect-type-mapping/spec.md`, requirement "Value-assertion effect inference") explicitly says "ReturnValue if present → first P0 → ReturnValue fallback" without accounting for generator yields. Both the spec and the code need updating.

## Goals / Non-Goals

**Goals:**

- Generator functions with value-type assertions map to `GeneratorYield` instead of `ReturnValue`
- Async generator functions with value-type assertions map to `AsyncGeneratorYield` instead of `ReturnValue`
- The generic assertion chain receives the same generator awareness (consistency)
- The spec is updated to reflect the corrected fallback chain
- Existing behavior for non-generator functions is unchanged

**Non-Goals:**

- Changing the error-check chain (generators don't raise errors via yield semantics — no change needed)
- Adding new assertion types or side-effect types
- Changing the P0/P1/P2 tier assignments of any effect type
- Modifying the detector to change how `GeneratorYield`/`AsyncGeneratorYield` are detected

## Decisions

### D1: Insert generator-yield check between P0 scan and ReturnValue fallback

**Decision**: In the value-type chain, after checking for `ReturnValue` and scanning P0 effects, check for `GeneratorYield` then `AsyncGeneratorYield` before falling back to `ReturnValue`.

**Rationale**: This preserves the existing priority order — `ReturnValue` and P0 effects still take precedence. Generator yields are checked only when no higher-priority match exists, which is the correct semantic: if a generator function also has a `ReturnValue` effect (shouldn't happen in practice, but defensively), `ReturnValue` wins. The order `GeneratorYield` before `AsyncGeneratorYield` follows the tier hierarchy (P1 before P2).

**Alternatives considered**:
- *Expand the P0 scan to include P1*: Too broad — would match many P1 effects (e.g., `SliceMutation`, `GlobalMutation`) that aren't semantically equivalent to return values. Generator yields are special because they are the generator equivalent of `ReturnValue`.
- *Check for generator yields first, before ReturnValue*: Semantically wrong — if both exist, `ReturnValue` is the more precise match.

### D2: Apply the same fix to the generic chain

**Decision**: In the generic chain, the current logic (`first effect if any, else ReturnValue`) already handles generators correctly because it returns the first detected effect regardless of tier. No change is needed for the match path. However, the fallback path (no effects at all) correctly returns `ReturnValue`, which is also fine — a function with no detected effects is not a generator.

**Updated assessment**: The generic chain is already correct. No code change needed for it.

### D3: Use direct string comparison, not tier lookup

**Decision**: Check for `GeneratorYield` and `AsyncGeneratorYield` by comparing `effect.type` against the `SideEffectType` enum values directly, not by scanning for "P1 tier effects" generically.

**Rationale**: The fix targets exactly two specific effect types that are semantically equivalent to return values in their respective contexts. A tier-based scan would be too broad and couple the mapping logic to tier assignments that could change.

## Risks / Trade-offs

**[Risk: A function has both ReturnValue and GeneratorYield]** → Mitigation: The chain checks `ReturnValue` first, so it wins. This shouldn't occur in practice (a function either returns or yields, not both in Python semantics), but the code handles it defensively.

**[Risk: Spec drift between test-mapping branch and this fix]** → Mitigation: This change modifies requirements in the existing `effect-type-mapping` spec using MODIFIED delta operations. When both branches merge, the archive step will integrate cleanly because the changes target different requirement text within the same requirement block.

**[Risk: New generator-like effect types added in future]** → Mitigation: The fix is explicit (names two specific types) rather than generic (scanning a tier). Future effect types would need an explicit addition here, which is the correct pattern — implicit tier-based matching could silently match unrelated effects.
