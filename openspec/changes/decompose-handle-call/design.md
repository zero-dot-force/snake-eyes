## Context

`_handle_call` in `_EffectVisitor` (detector.py:657-1267) is a single
method that resolves every call expression to its `SideEffectType`. It is
a ~610-line ordered `if/elif` waterfall with cyclomatic complexity 144,
suppressed by `# noqa: C901 (complex)`.

Constraints:
- **Deterministic output** (constitution I): handler dispatch order must
  be fixed. A dict-keyed dispatch would risk non-deterministic iteration.
- **Detection accuracy** (constitution II): the exact set, order, and
  content of emitted effects is locked by existing golden tests
  (`test_p0_golden_full_equality`, `test_p3_positive_effects`, the issue-#18
  ambiguity suite, and `test_detector_extra.py`).
- **Python-native** (constitution III): `ast` only, no new dependencies.
- **Testability** (constitution IV): every handler testable in isolation.
- **Analysis safety** (constitution V): static only, unchanged.

The `_EffectVisitor` already carries all the state handlers need
(`import_aliases`, `open_vars`, `param_names`, `global_names`,
`nonlocal_names`, `local_func_names`, `local_binding_names`,
`module_func_names`, `enclosing_bindings`, `is_async`, plus `_add`).

## Goals / Non-Goals

**Goals:**
- Reduce `_handle_call` to a thin dispatcher whose complexity is
  proportional to the number of handlers, not the number of branches.
- Preserve emitted effects exactly (set, order, description, target,
  location, detail).
- Make each dispatch rule an isolated, directly-testable method.
- Remove the `# noqa: C901` suppression.

**Non-Goals:**
- Changing any detection rule, effect, or confidence value.
- Adding new effects or expanding the `SideEffectType` taxonomy.
- Renaming visitor fields or threading new parameters through the call
  chain.
- Addressing the other moderate-complexity functions (issue #27).
- Using astroid or any new inference in the effect hot path.

## Decisions

### D1: Ordered handler chain instead of if/elif waterfall

**Decision**: Convert `_handle_call` into a dispatcher that iterates an
ordered tuple of bound-method handlers and returns on the first `True`:

```python
def _handle_call(self, node: ast.Call) -> None:
    fn = node.func
    for handler in self._CALL_HANDLERS:
        if handler(self, node, fn):
            return
    self._handle_name_call_fallback(node, fn)
```

Each handler has the signature `_handle_*(self, node: ast.Call, fn: ast.expr)
-> bool`, returning `True` when it emitted and consumed the call, `False`
to fall through.

**Rationale**: A tuple preserves source order deterministically and is
trivial to read and extend. Each handler is independently unit-testable.
The existing waterfall already returns after every emission, so the
short-circuit semantics map 1:1.

**Alternatives considered**:
- *Dict/registry keyed by call kind*: Rejected — the rules are ordered
  and overlapping (e.g. a `.write()` on an open-var is checked before the
  generic writer rule), so a hash lookup cannot express precedence and
  risks non-deterministic ordering.
- *Match statements on node shape*: Rejected — `ast` node dispatch does
  not capture the many name/method-set combinations cleanly and would
  re-centralize complexity.

### D2: Handler granularity — top-level clusters + method-call sub-concerns

**Decision**: Group the ~34 emission rules into 14 top-level handlers and
14 method-call sub-handlers, each mapping to a small, named concern:

Top-level:
- `_handle_exit_calls` — `sys.exit` / `os._exit` (ProcessExit + ErrorSignal)
- `_handle_print_call` — `print` (StdoutWrite / StderrWrite)
- `_handle_dynamic_exec` — `eval`/`exec` (CallbackInvocation ambiguous)
- `_handle_reflection_calls` — `setattr`/`delattr` (MonkeyPatch /
  ReflectionMutation)
- `_handle_metaprogramming` — `type(...)` / `types.new_class`
- `_handle_import_effects` — `__import__` / `importlib.import_module`
- `_handle_finalizers` — `atexit.register` / `weakref.finalize`
- `_handle_time_dependency` — time / datetime / date
- `_handle_logging` — logging / logger / log
- `_handle_concurrency` — gather / create_task / run_in_executor / Pool
- `_handle_open_write` — `open(...,'w')` standalone
- `_handle_computed_getattr_call` — `getattr(...)()`
- `_handle_name_call_fallback` — pure builtins, locals, module resolution,
  ambiguous fallthrough

Method-call (`ast.Attribute`) sub-concerns (dispatched from a
`_handle_method_calls` coordinator):
- `_handle_std_streams` — `sys.stdout.write` / `sys.stderr.write`
- `_handle_env_mutations` — `os.environ` / `os.putenv` / `environ`
- `_handle_os_filesystem` — remove/unlink/rmdir/chmod/chown/rename/mkdir/
  makedirs/symlink/link/write
- `_handle_shutil_and_path` — shutil copy*/rmtree + Path write_text/
  write_bytes/unlink/mkdir/rename/chmod
- `_handle_thread_spawn` — `.start()` (GoroutineSpawn)
- `_handle_mutex_op` — acquire/release (MutexOp)
- `_handle_channel_send` — put/put_nowait (ChannelSend)
- `_handle_task_cancel` — `.cancel()` (ContextCancellation)
- `_handle_barrier_wait` — `.wait()` (WaitGroupOp)
- `_handle_db_methods` — execute/executemany + commit/rollback
- `_handle_http_response` — response write (HTTPResponseWrite)
- `_handle_writer_methods` — `.write`/`.writelines`/`.flush` with
  StreamOutput vs WriterOutput co-emit logic
- `_handle_container_methods` — receiver/param/container precedence
- `_handle_map_methods` — param vs MapMutation precedence

**Rationale**: Each helper stays small (well under the C901 threshold)
and named by the effect it detects, matching the repo's existing
`_collect_*` / `_is_*` naming convention.

**Alternatives considered**:
- *One helper per single effect type*: Rejected — many effects share a
  single name/attribute test (e.g. time vs datetime vs date are one
  check); over-splitting multiplies boilerplate without added clarity.

### D3: Preserve method-call evaluation order

**Decision**: Keep the *exact* current ordering of checks inside the
method-call coordinator. No rule is reordered, merged, or split across
handlers in a way that changes which branch fires first.

**Rationale**: The `.write()` open-var co-emit, the container-vs-param-vs-
receiver precedence, and the std-stream/env checks are order-sensitive.
The existing golden tests will catch any accidental reordering.

**Alternatives considered**:
- *Reordering by tier or by "likelihood"*: Rejected — would change
  behavior and is not the goal of a refactor.

### D4: No parameter/field renames

**Decision**: Keep `local_func_names`, `module_func_names`, `open_vars`,
and all other visitor state names unchanged. Handlers read the same
`self.*` attributes.

**Rationale**: Renaming threads through `_analyze_func_node` and the
module walker for no behavioral benefit. The refactor should be a pure
move.

**Alternatives considered**:
- *Rename to `local_callable_names`*: Deferred (see prior issue-#18
  decision D4); out of scope here.

### D5: Tests lock behavior, not structure

**Decision**: Per-handler tests exercise each handler through
`analyze_source(...)` with inline source strings, asserting the full
effect list (not just membership) — the same pattern as the existing
detector tests. No test is written against a private `_handle_*` method
directly.

**Rationale**: The public contract is the emitted effect list. Testing via
the public entry point keeps tests meaningful if handler names later
change, while still giving per-rule coverage.

**Alternatives considered**:
- *Direct unit tests of private handlers*: Rejected — brittle and
  duplicates the existing golden pattern.

## Risks / Trade-offs

- **[Risk] Ordering-sensitive co-emit regressions** (StreamOutput +
  conditional FileSystemWrite; container/param/receiver precedence).
  → **Mitigation**: D3 preserves order verbatim; the existing golden and
  negative tests (`test_file_write_is_stream_output_not_writer_output`,
  `test_self_append_is_receiver_not_container`,
  `test_param_append_is_pointer_not_container`) guard this.
- **[Risk] Coverage drop from newly introduced helper methods**.
  → **Mitigation**: one exercising test per handler; CI runs the 85%
  gate.
- **[Risk] mypy --strict friction on new signatures**.
  → **Mitigation**: `fn: ast.expr`, `node: ast.Call`, explicit `-> bool`
  returns; `_CALL_HANDLERS` typed as a tuple of callables.
- **[Risk] Divergence between handler name and effect emitted**.
  → **Mitigation**: keep the existing `_add(SideEffectType.X, ...)` calls
  verbatim inside each handler during the move.

## Migration Plan

Pure internal refactor, no runtime/migration concerns. Rollback is a git
revert of the change; no data or schema is affected.

## Open Questions

None — the refactor is mechanical and the target structure is fully
determined by the current waterfall.
