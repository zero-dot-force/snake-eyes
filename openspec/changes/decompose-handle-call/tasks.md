## 1. Establish the handler-chain scaffold

- [x] 1.1 Add a `_CALL_HANDLERS` ordered tuple of bound-method names and a thin `_handle_call` dispatcher that iterates it and short-circuits on first `True`
- [x] 1.2 Define the handler signature `_handle_*(self, node: ast.Call, fn: ast.expr) -> bool` and type the handler registry for mypy strict
- [x] 1.3 Remove the `# noqa: C901 (complex)` suppression from `_handle_call`

## 2. Extract top-level call clusters

- [x] 2.1 `_handle_exit_calls` — `sys.exit` / `os._exit` (ProcessExit + ErrorSignal)
- [x] 2.2 `_handle_print_call` — `print(...)` (StdoutWrite / StderrWrite)
- [x] 2.3 `_handle_dynamic_exec` — `eval` / `exec` (CallbackInvocation ambiguous)
- [x] 2.4 `_handle_reflection_calls` — `setattr` / `delattr` (MonkeyPatch / ReflectionMutation)
- [x] 2.5 `_handle_metaprogramming` — `type(...)` 3-arg / `types.new_class`
- [x] 2.6 `_handle_import_effects` — `__import__` / `importlib.import_module`
- [x] 2.7 `_handle_finalizers` — `atexit.register` / `weakref.finalize`
- [x] 2.8 `_handle_time_dependency` — time / datetime / date
- [x] 2.9 `_handle_logging` — logging / logger / log
- [x] 2.10 `_handle_concurrency` — gather / create_task / run_in_executor / Pool
- [x] 2.11 `_handle_open_write` — `open(...,'w')` standalone
- [x] 2.12 `_handle_computed_getattr_call` — `getattr(...)()`
- [x] 2.13 `_handle_name_call_fallback` — pure builtins, locals, module resolution, ambiguous fallthrough

## 3. Split the method-call block

- [x] 3.1 `_handle_std_streams` — `sys.stdout.write` / `sys.stderr.write`
- [x] 3.2 `_handle_env_mutations` — `os.environ` / `os.putenv` / `environ`
- [x] 3.3 `_handle_os_filesystem` — remove/unlink/rmdir/chmod/chown/rename/mkdir/makedirs/symlink/link/write
- [x] 3.4 `_handle_shutil_and_path` — shutil copy*/rmtree + Path write_text/write_bytes/unlink/mkdir/rename/chmod
- [x] 3.5 `_handle_thread_spawn` — `.start()` (GoroutineSpawn)
- [x] 3.6 `_handle_mutex_op` — acquire/release (MutexOp)
- [x] 3.7 `_handle_channel_send` — put/put_nowait (ChannelSend)
- [x] 3.8 `_handle_task_cancel` — `.cancel()` (ContextCancellation)
- [x] 3.9 `_handle_barrier_wait` — `.wait()` (WaitGroupOp)
- [x] 3.10 `_handle_db_methods` — execute/executemany + commit/rollback
- [x] 3.11 `_handle_http_response` — response write (HTTPResponseWrite)
- [x] 3.12 `_handle_writer_methods` — `.write`/`.writelines`/`.flush` StreamOutput vs WriterOutput co-emit
- [x] 3.13 `_handle_container_methods` — receiver/param/container precedence
- [x] 3.14 `_handle_map_methods` — param vs MapMutation precedence
- [x] 3.15 Add a `_handle_method_calls` coordinator that dispatches 3.1-3.14 in the original order

## 4. Tests

- [x] 4.1 Add one positive test per handler (top-level + method-call), asserting the full effect list via `analyze_source`
- [x] 4.2 Add negative/ordering regressions for the write-mode open co-emit and container/param/receiver precedence
- [x] 4.3 Confirm all existing golden tests (`test_p0_golden_full_equality`, `test_p3_positive_effects`, issue-#18 ambiguity suite, `test_detector_extra.py`) pass unchanged

## 5. Verification

- [x] 5.1 Run `uv run ruff check src/ tests/` — must pass
- [x] 5.2 Run `uv run ruff format --check src/ tests/` — must pass
- [x] 5.3 Run `uv run mypy src/` — must pass
- [x] 5.4 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85` — must pass with ≥85% coverage
