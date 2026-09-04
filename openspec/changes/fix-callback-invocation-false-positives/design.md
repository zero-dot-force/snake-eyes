## Context

The `ast.Name` fallthrough in `_handle_call` (detector.py:1233-1247)
is the final fallthrough for `ast.Name` calls. It checks two
allowlists — `_PURE_BUILTINS` (stdlib builtins) and
`local_func_names` (module-level + nested function defs) — and emits
`CallbackInvocation` with `confidence: ambiguous` for anything not
matched.

The visitor already receives `import_aliases: dict[str, str]` (line
412), which maps local names to their fully-qualified module paths.
It also already uses `import_aliases` for MonkeyPatch detection (line
566) and method-call analysis (line 1194). However, `_handle_call`
never consults it.

The module-level `_analyze_tree` function (line 1672) already
collects `module_func_names` from the AST. Class names could be
collected the same way.

Constraints:
- The detector spec requires "ambiguous constructs reported, never
  dropped" — but class constructors are NOT genuinely ambiguous.
  They are deterministic object instantiations. Suppressing them is
  correctness, not dropping ambiguity.
- Constitution principle 2 (Detection Accuracy): false positives are
  bugs, just like false negatives.

## Goals / Non-Goals

**Goals:**
- Eliminate false `CallbackInvocation` for imported names (classes,
  functions, constants) by consulting `import_aliases`
- Eliminate false `CallbackInvocation` for same-module class
  constructors by collecting `ClassDef` names alongside
  `module_func_names`
- Add PascalCase heuristic as a safety net for edge cases where
  imports and class defs are not sufficient (e.g., dynamic imports,
  star imports)
- Maintain detection of genuinely ambiguous callbacks (lowercase
  names not resolvable through any mechanism)

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

### D1: Expanded call resolution strategy

**Decision**: Apply four checks in sequence before falling through
to `CallbackInvocation` (two existing, two new):

1. `_PURE_BUILTINS` (existing) — no change
2. `local_func_names` (existing) — expand to include `ClassDef` names
3. `import_aliases` (new check) — names present in imports are known
   symbols
4. PascalCase heuristic (new check) — `re.match(r'^[A-Z][a-zA-Z0-9]*$', name)`
   as final safety net

**Rationale**: Each layer catches different cases with zero overlap
cost. The ordering is most-specific-first (builtins → local defs →
imports → convention heuristic). All four checks together cover the
vast majority of constructor false positives.

**Alternatives considered**:
- *Import-only*: Would miss same-module classes. Rejected.
- *PascalCase-only*: Would miss lowercase factory functions from
  imports (e.g., `namedtuple(...)`). Also too heuristic-heavy.
  Rejected as sole mechanism.
- *Astroid type inference*: Too expensive for the hot path and
  already used in `inference.py` for a different purpose
  (caller-count signals, not effect detection). Rejected.

### D2: Expand `local_func_names` to include `ClassDef` names

**Decision**: In `_analyze_tree`, collect `ClassDef` names into the
same `module_func_names` set (see D4 — rename deferred). In
`_analyze_single_function`, also collect nested
`ClassDef` names into `local_func_names`.

**Rationale**: Class constructors are statically-resolvable local
callables, same as function defs. The existing `local_func_names`
mechanism is the right place — no new data structures needed.

**Alternatives considered**:
- *Separate `module_class_names` set*: Adds a new parameter
  threaded through the entire call chain. More precise naming but
  higher coupling cost for no behavioral difference. Rejected.

### D3: PascalCase as heuristic, not authoritative

**Decision**: The PascalCase check runs last and only when all other
resolution fails. It uses a simple regex (`^[A-Z][a-zA-Z0-9]*$`)
without requiring exact PEP 8 compliance.

**Rationale**: PascalCase is a convention, not a guarantee. Using it
as a last-resort heuristic avoids false negatives (a PascalCase
callback would be silently skipped) but acceptable because:
- PascalCase callbacks are vanishingly rare in practice
- The PascalCase check only fires for names not in imports or class
  defs, meaning the name is truly unknown
- Better to err toward suppressing a rare PascalCase callback than
  to emit 729+ false positives for constructors

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

- **[Risk] PascalCase false negative**: A PascalCase-named callback
  variable (e.g., `Handler = get_handler(); Handler()`) would not
  trigger `CallbackInvocation`. → **Mitigation**: This is an
  extremely rare pattern, and such code would likely trigger other
  effects (the assignment from `get_handler()` would be flagged).
  Acceptable trade-off given 729+ false positives eliminated.

- **[Risk] Import of side-effectful callable**: An imported function
  like `shutil.rmtree` called as `rmtree(path)` would no longer
  emit `CallbackInvocation`. → **Mitigation**: This is correct
  behavior — `rmtree` is a known name, not an opaque callback. Its
  actual effects (file deletion) would be detected by the attribute
  call handler or by Gaze's cross-module analysis. The
  `CallbackInvocation` type is specifically for *opaque* callbacks.

- **[Risk] Star imports**: `from module import *` does not populate
  `import_aliases` for individual names. → **Mitigation**: PascalCase
  heuristic catches class constructors from star imports. Lowercase
  names from star imports remain flagged as `CallbackInvocation`,
  which is arguably correct (star imports ARE ambiguous).
