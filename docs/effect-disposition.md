# Effect Disposition Table

This table records the classification judgment exercised by snake-eyes'
surface-aware `visibility` signal. It is **documentation**, not a runtime
input: snake-eyes never reads this file. Dispositions are documentation terms,
not snake-eyes scoring labels — they record the visibility signal's intended
direction (public → toward `contractual`, private → toward `incidental`), not a
guaranteed final Gaze bucket.

The disposition `unclaimed` here denotes "no classification judgment asserted"
(Gaze may bucket it `ambiguous`) and is distinct from the
container-mutation-assertion coverage domain's `unclaimed`, which denotes a
`ContainerMutation` effect no test assertion covers.

Key: `(surface, enclosing-class visibility, dunder, name-prefix, effect-type exception)`.

Columns:
- **surface** — where the function is defined: `module` (top-level), `method` (directly inside a class body), `nested` (directly inside a function body).
- **enclosing-class visibility** — for `method` surfaces: `public`/`private` (a class is `private` when its name has a leading underscore or it is transitively nested inside a function body); `none` for `module`/`nested`.
- **dunder** — `true` when the name starts and ends with `__`; `n/a` when it does not decide the disposition.
- **name-prefix** — `private` for a leading-underscore name, `public` otherwise; a leading-underscore module-level name listed in `__all__` counts as `public` (caller-visible). `n/a` when it does not decide.
- **effect-type exception** — `ClosureCaptureMutation` (the one nested effect that stays `unclaimed`); otherwise `none`.

| surface | enclosing-class visibility | dunder | name-prefix | effect-type exception | disposition | rationale |
| --- | --- | --- | --- | --- | --- | --- |
| module | none | false | public | none | contractual | Caller-visible module API, e.g. ReturnValue, GeneratorYield, StreamOutput. |
| module | none | false | private | none | incidental | Private module helper bookkeeping, e.g. GlobalMutation, EnvVarMutation. |
| module | none | true | n/a | none | unclaimed | Module-level dunder emits no signal, e.g. ReturnValue. |
| method | public | false | public | none | contractual | Public method API, e.g. ReturnValue, ReceiverMutation. |
| method | public | false | private | none | incidental | Private method helper, e.g. ContainerMutation, MapMutation. |
| method | public | true | n/a | none | contractual | Dunder method of a public class, e.g. ReceiverMutation (`__init__`). |
| method | private | false | n/a | none | incidental | Method of a private class, e.g. MapMutation. |
| method | private | true | n/a | none | incidental | Dunder method of a private class, e.g. ReceiverMutation. |
| nested | none | n/a | n/a | none | incidental | Nested helper bookkeeping, e.g. ContainerMutation. |
| nested | none | n/a | n/a | ClosureCaptureMutation | unclaimed | Nested closure can escape and be caller-visible, e.g. ClosureCaptureMutation. |
