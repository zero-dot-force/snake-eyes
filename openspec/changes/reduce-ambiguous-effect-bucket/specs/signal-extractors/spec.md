## Relationship to Prior Spec

This delta modifies the `signal-extractors` capability spec
([signal-extractors spec](../../../classify-signals/specs/signal-extractors/spec.md))
from the `classify-signals` change. The prior spec's "visibility extractor
distinguishes public and private names" requirement defined the `visibility`
extractor strictly by name and `__all__` membership, deferring dunder behavior to gaze-py's documented behavior. This delta makes the extractor surface-aware.

## MODIFIED Requirements

### Requirement: visibility extractor distinguishes public and private names

Previously: the `visibility` extractor emitted a `visibility` signal based only
on the function's public/private naming convention (leading-underscore private
vs. public) and `__all__` membership; the shipped extractor returned `None` for dunder methods (`__x__`) (the prior spec deferred dunder behavior to gaze-py's documented behavior).

The `visibility` extractor SHALL now also accept the function's surface
(`module`, `method`, `nested`), the enclosing-class visibility (`none`,
`public`, `private`), and the effect type of the effect being classified.
Dunder-ness SHALL be re-derived from the function name (it is not a
parameter).

The extractor SHALL apply, in priority order:

1. A `nested` surface SHALL emit `PRIVATE_WEIGHT` (`-10`), EXCEPT for
   `ClosureCaptureMutation`, for which the extractor SHALL return `None`
   (no signal) — a nested closure can escape and be caller-visible, so its
   disposition is `unclaimed`.
2. Dunder methods: a dunder method of a `public`-visibility class SHALL emit
   `PUBLIC_WEIGHT` (`10`); a dunder method of a `private`-visibility class
   SHALL emit `PRIVATE_WEIGHT` (`-10`); a module-level dunder function SHALL
   return `None` (prior behavior).
3. Non-dunder methods of a `private`-visibility class SHALL emit
   `PRIVATE_WEIGHT` (`-10`), regardless of the method's own name.
4. All remaining module-level and `public`-visibility-class non-dunder
   functions SHALL preserve the prior name/`__all__` rules: listed in
   `__all__` SHALL emit `PUBLIC_WEIGHT` (`10`), a leading-underscore name
   SHALL emit `PRIVATE_WEIGHT` (`-10`), otherwise `PUBLIC_WEIGHT` (`10`).

The extractor SHALL use only the existing `PUBLIC_WEIGHT` (`10`) and
`PRIVATE_WEIGHT` (`-10`) gate values, SHALL NOT introduce a new `source`
value, and SHALL NOT emit any classification label.

#### Scenario: dunder method of a public class emits public visibility

- **WHEN** the extractor runs for `__init__` defined on a class whose visibility is `public`
- **THEN** it emits a `visibility` signal with weight `PUBLIC_WEIGHT` (`10`)

#### Scenario: dunder method of a private class emits private visibility

- **WHEN** the extractor runs for `__init__` defined on a class whose visibility is `private`
- **THEN** it emits a `visibility` signal with weight `PRIVATE_WEIGHT` (`-10`)

#### Scenario: nested helper emits private visibility

- **WHEN** the extractor runs for a nested helper named `helper` (no leading underscore)
- **THEN** it emits a `visibility` signal with weight `PRIVATE_WEIGHT` (`-10`)

#### Scenario: nested dunder helper still emits private visibility

- **WHEN** the extractor runs for a nested function named `__x__`
- **THEN** it emits a `visibility` signal with weight `PRIVATE_WEIGHT` (`-10`) (the nested rule precedes the dunder rule; only module-level dunders return `None`)

#### Scenario: nested closure-capture effect emits no signal

- **WHEN** the extractor runs for a `ClosureCaptureMutation` effect on a `nested` surface
- **THEN** it returns `None` (no `visibility` signal)

#### Scenario: private-named method on a public class emits private visibility

- **WHEN** the extractor runs for a method `def _helper()` on a class whose visibility is `public`
- **THEN** it emits a `visibility` signal with weight `PRIVATE_WEIGHT` (`-10`)

#### Scenario: public-named method on a public class emits public visibility

- **WHEN** the extractor runs for a method `def run()` on a class whose visibility is `public`
- **THEN** it emits a `visibility` signal with weight `PUBLIC_WEIGHT` (`10`)

#### Scenario: method on a private class is private regardless of name

- **WHEN** the extractor runs for a method `def run()` on a class whose visibility is `private`
- **THEN** it emits a `visibility` signal with weight `PRIVATE_WEIGHT` (`-10`)

#### Scenario: module-level dunder keeps prior behavior

- **WHEN** the extractor runs for a module-level `__x__` function
- **THEN** it returns `None` (no `visibility` signal)

#### Scenario: prior name and __all__ behavior preserved

- **WHEN** the extractor runs for a module-level or public-class non-dunder function
- **THEN** the prior name/`__all__` rules apply unchanged (listed in `__all__` emits `PUBLIC_WEIGHT`, a leading-underscore name emits `PRIVATE_WEIGHT`, otherwise `PUBLIC_WEIGHT`)

#### Scenario: no classification label and no new source introduced

- **WHEN** the surface-aware extractor emits a signal
- **THEN** the extractor adds no fields beyond `weight` and `reasoning`, the emitted wire dict keeps its existing `function`/`package`/`side_effect_type`/`source`/`weight`/`reasoning` shape, and no label field, no new `source` value, and no classification term in `reasoning` is introduced
