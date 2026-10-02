## ADDED Requirements

### Requirement: function surface classification

The signal adapter SHALL compute, for every analyzed function, a **function surface** value describing where the function is defined: `module` (top-level), `method` (directly inside a class body), or `nested` (directly inside another function body). A function whose direct enclosing scope is a class body SHALL be `method`, even if that class is itself nested inside a function; a function whose direct enclosing scope is a function body SHALL be `nested`. Surface SHALL be derived with the stdlib `ast` from the same deterministic file set already enumerated by `_collect_file_context`, and SHALL NOT execute analyzed code. The classification SHALL be exposed as `_FileContext.surface_by_line`, a `dict[int, FunctionSurface]` keyed by the function's `lineno`.

#### Scenario: module-level function classified as module

- **WHEN** the adapter processes `def f(): ...` at module scope
- **THEN** `f` is classified with surface `module`

#### Scenario: method classified as method

- **WHEN** the adapter processes a `def f` directly inside a class body
- **THEN** `f` is classified with surface `method`

#### Scenario: nested helper classified as nested

- **WHEN** the adapter processes a `def helper` defined directly inside another function body
- **THEN** `helper` is classified with surface `nested`

#### Scenario: method on a class nested inside a function is still method

- **WHEN** the adapter processes `def outer(): class Worker: def run(self): ...`
- **THEN** `run` is classified with surface `method` (not `nested`)

### Requirement: enclosing-class visibility classification

The signal adapter SHALL compute, for `method` surfaces, an **enclosing-class visibility** value of `public` or `private`; for `module` and `nested` surfaces it SHALL be `none`. The enclosing-class visibility SHALL be `private` when the enclosing class name has a leading underscore OR the enclosing class is transitively nested inside a function body (any ancestor scope of the class is a function body — a function-local class is not caller-visible regardless of its name); otherwise it SHALL be `public`. The visibility SHALL be exposed as `_FileContext.enclosing_class_visibility_by_line`, a `dict[int, EnclosingClassVisibility]` keyed by the function's `lineno`.

#### Scenario: method on a private-named class is private

- **WHEN** the adapter processes `def run` inside `class _Worker:`
- **THEN** `run`'s enclosing-class visibility is `private`

#### Scenario: method on a public-named class is public

- **WHEN** the adapter processes `def run` inside `class Worker:`
- **THEN** `run`'s enclosing-class visibility is `public`

#### Scenario: class nested inside a function is private regardless of name

- **WHEN** the adapter processes `def factory(): class Worker: def run(self): ...`
- **THEN** `run`'s enclosing-class visibility is `private`

#### Scenario: class nested inside another class is public

- **WHEN** the adapter processes `class Outer: class Inner: def run(self): ...`
- **THEN** `run`'s enclosing-class visibility is `public`

#### Scenario: class transitively nested inside a function is private

- **WHEN** the adapter processes `def factory(): class Outer: class Inner: def run(self): ...`
- **THEN** `run`'s enclosing-class visibility is `private` (an ancestor of `Inner` is a function body)

#### Scenario: class nested inside a private class does not inherit private

- **WHEN** the adapter processes `class _Outer: class Inner: def run(self): ...` at module scope
- **THEN** `run`'s enclosing-class visibility is `public` (only the direct enclosing class name decides)

#### Scenario: module and nested surfaces have no enclosing-class visibility

- **WHEN** the adapter processes a module-level function or a nested helper
- **THEN** its enclosing-class visibility is `none`
