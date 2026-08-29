## ADDED Requirements

### Requirement: detector public API
The system SHALL provide `analyze_path(root_path: str, patterns: list[str]) -> list[FunctionRecord]` as the production entry point and `analyze_source(source: str, filename: str, package: str) -> list[FunctionRecord]` for analyzing a single in-memory source string. `analyze_path` SHALL run `discovery.discover()` and analyze the ordered concatenation of the sorted `source_files` then `test_files`, de-duplicated preserving first occurrence.

#### Scenario: analyze_path returns records for discovered files
- **WHEN** `analyze_path` runs over a tree containing a function with observable effects
- **THEN** it returns a list of `FunctionRecord` covering the discovered `.py` files

#### Scenario: analyze_source analyzes a single source string
- **WHEN** `analyze_source("def f():\n    return 1\n", "m.py", "m")` is called
- **THEN** it returns one `FunctionRecord` named `f` for that source without touching the filesystem

### Requirement: one function record per definition
The detector SHALL emit one `FunctionRecord` for every `def` and `async def`, including nested functions and methods of nested classes. The record `name` SHALL be the unqualified definition name (not `outer.inner`). Two definitions sharing a name SHALL each produce a record distinguished by `line`. Lambdas SHALL NOT produce a `FunctionRecord`.

#### Scenario: nested function gets its own record
- **WHEN** a module defines `def outer():` containing `def inner():`
- **THEN** both `outer` and `inner` appear as separate records, each with the unqualified name

#### Scenario: duplicate nested names both emitted
- **WHEN** two nested functions share the same name at different lines
- **THEN** two records are emitted with the same `name` and different `line`

#### Scenario: lambda is not a function record
- **WHEN** a module contains `f = lambda x: x + 1`
- **THEN** no `FunctionRecord` is emitted for the lambda

### Requirement: effect record shape
Each detected effect SHALL serialize as `{type, description, location}`. The `location` field SHALL always be present as `"<file>.py:<line>:<col>"`. The `target` and `detail` fields are OPTIONAL and SHALL be omitted when not applicable (per `function_record_to_dict`). The `detail` field SHALL carry Python-specific metadata only (for example `{"exception_class": "ZeroDivisionError"}` or `{"confidence": "ambiguous"}`). The detector SHALL NOT set a `classification` field on any effect (Gaze performs classification).

#### Scenario: location includes file, line, and column
- **WHEN** an effect is detected on a statement in `p0.py`
- **THEN** its `location` contains `p0.py` and the statement's line and column

#### Scenario: no classification field on effects
- **WHEN** any effect is serialized
- **THEN** the effect object has no `classification` key

#### Scenario: effect without natural target omits target key
- **WHEN** a `ReturnValue`, `GeneratorYield`, or `ProcessExit` effect is serialized
- **THEN** the serialized object contains `type`, `description`, and `location` but does NOT contain a `target` key

### Requirement: P0 return and error detection
The detector SHALL detect the P0 types `ReturnValue`, `ErrorReturn`, and `ErrorSignal`. A `return` with a non-`None` value SHALL emit `ReturnValue`; a bare `return` and `return None` SHALL also emit `ReturnValue`. Every `raise` statement SHALL emit `ErrorSignal`. A `raise` of an instance, call, or name SHALL additionally emit `ErrorReturn` at the same location — **except** for the SystemExit family: `raise SystemExit`, `raise SystemExit(...)`, `sys.exit(...)`, and `os._exit(...)` MUST NOT emit `ErrorReturn` (they emit `ProcessExit` + `ErrorSignal` instead; see "control-flow and process effect detection"). A bare `raise` (re-raise) SHALL emit BOTH `ErrorReturn` and `ErrorSignal` at the same location. Missing any P0 effect present in a fixture is a release-blocking defect.

#### Scenario: return value detected
- **WHEN** a function contains `return 42`
- **THEN** a `ReturnValue` effect is emitted at that return

#### Scenario: bare return counts as ReturnValue
- **WHEN** a function contains a bare `return`
- **THEN** a `ReturnValue` effect is emitted

#### Scenario: raise detected as ErrorReturn and ErrorSignal
- **WHEN** a function contains `raise ValueError("bad")`
- **THEN** both an `ErrorReturn` and an `ErrorSignal` effect are emitted at the same location

#### Scenario: bare re-raise emits both ErrorReturn and ErrorSignal
- **WHEN** a function contains a bare `raise` (re-raise with no argument)
- **THEN** both an `ErrorReturn` effect and an `ErrorSignal` effect are emitted at the same location

### Requirement: ErrorSignal dual-emit
For every `raise` statement the detector SHALL emit an `ErrorSignal` effect in addition to the appropriate `ErrorReturn` effect, at the same location. This applies to raises of instances, calls, names, and bare re-raises alike. `ErrorSignal` is both a P0 type and one of the Python-specific types.

#### Scenario: raise emits both ErrorReturn and ErrorSignal
- **WHEN** a function contains `raise ValueError("bad")`
- **THEN** both an `ErrorReturn` and an `ErrorSignal` effect are emitted at the same location

### Requirement: sentinel error detection
The detector SHALL emit `SentinelError` for a module-level class that subclasses `Exception` or `BaseException` and is used as a sentinel, matching the gaze-py sentinel scan.

#### Scenario: module-level exception subclass detected
- **WHEN** a module defines `class MyError(Exception): pass` at module level
- **THEN** a `SentinelError` effect is associated with that sentinel

### Requirement: receiver and argument mutation detection
The detector SHALL detect the P0 types `ReceiverMutation` and `PointerArgMutation`. Assignment or augmented assignment to `self.x`, or a mutating call on `self.x`, SHALL emit `ReceiverMutation`. A mutating call, or item/attribute assignment, on a parameter other than `self`/`cls` SHALL emit `PointerArgMutation`.

#### Scenario: self attribute assignment detected
- **WHEN** a method contains `self.value = 1`
- **THEN** a `ReceiverMutation` effect is emitted

#### Scenario: parameter mutation detected
- **WHEN** a function `def f(items):` contains `items.append(1)`
- **THEN** a `PointerArgMutation` effect is emitted

### Requirement: container and collection mutation detection
The detector SHALL emit `ContainerMutation` for mutating methods (`append`, `extend`, `insert`, `remove`, `pop`, `clear`, `reverse`, `sort`, `add`, `discard`, `update`) invoked on a local or unknown-origin object. When the target is `self.*` the detector SHALL prefer `ReceiverMutation`; when the target is a parameter it SHALL prefer `PointerArgMutation`. The detector SHALL also detect `SliceMutation` (list/bytearray item or slice assignment, or list mutating methods on a local list), `MapMutation` (dict item assignment or dict mutating methods), and `GlobalMutation` (assignment to a name declared `global`).

#### Scenario: local container mutation detected
- **WHEN** a function contains `xs = []` followed by `xs.append(1)`
- **THEN** a `ContainerMutation` effect is emitted for `xs.append`

#### Scenario: global assignment detected
- **WHEN** a function declares `global counter` and assigns `counter = 1`
- **THEN** a `GlobalMutation` effect is emitted

### Requirement: output and stream effect detection
The detector SHALL emit `StdoutWrite` for `print(...)` and `sys.stdout.write`, `StderrWrite` for `sys.stderr.write` and `print(..., file=sys.stderr)`, and `WriterOutput` for `.write`/`.writelines`/`.flush` on an object that is not stdout/stderr and whose file-ness cannot be proven. It SHALL emit `StreamOutput` for `.write` on a concretely-opened or passed-in file object; `StreamOutput` SHALL NOT be emitted for `print` calls (which `StdoutWrite`/`StderrWrite` already cover). **Precedence:** a `.write` on a concretely-opened or passed-in file object emits `StreamOutput` ONLY — NOT `WriterOutput`; `WriterOutput` applies to `.write`/`.writelines`/`.flush` on non-stdio objects that are not file-like. For a parameter whose file-ness cannot be proven without inference (no astroid in v1), the default is `WriterOutput` — do NOT double-emit both `StreamOutput` and `WriterOutput` for the same call. A file opened in write mode (e.g. `'w'`, `'a'`, `'x'`, or `'+'`) MAY co-emit `FileSystemWrite` in addition to `StreamOutput`. It SHALL emit `HTTPResponseWrite` for framework response writes matched by name (`response.write`, `make_response`, `HttpResponse`).

#### Scenario: print detected as StdoutWrite
- **WHEN** a function contains `print("hi")`
- **THEN** a `StdoutWrite` effect is emitted and no `StreamOutput` effect is emitted for the same call

#### Scenario: file write detected as StreamOutput
- **WHEN** a function opens a file with `open("out.txt", "w")` and calls `.write` on the file object
- **THEN** a `StreamOutput` effect is emitted (and may co-emit `FileSystemWrite`); no `StdoutWrite` is emitted

### Requirement: filesystem effect detection
The detector SHALL emit `FileSystemWrite` for `open(..., 'w'|'a'|'x'|'+')`, `Path.write_text`/`write_bytes`, `os.write`, and `shutil.copy*`; `FileSystemDelete` for `os.remove`/`unlink`/`rmdir`, `Path.unlink`, and `shutil.rmtree`; and `FileSystemMeta` for `os.chmod`/`chown`/`rename`/`mkdir` and `Path.mkdir`/`rename`/`chmod`.

#### Scenario: write-mode open detected
- **WHEN** a function contains `open("out.txt", "w")`
- **THEN** a `FileSystemWrite` effect is emitted

### Requirement: environment, reflection, and closure mutation detection
The detector SHALL emit `EnvVarMutation` for `os.environ[...] = ...`, `os.putenv`, and `os.environ.update`; `ReflectionMutation` for `setattr` on arbitrary objects, `delattr`, and `__dict__` writes; and `ClosureCaptureMutation` for assignment to a name declared `nonlocal`.

#### Scenario: environment mutation detected
- **WHEN** a function contains `os.environ["X"] = "1"`
- **THEN** an `EnvVarMutation` effect is emitted

#### Scenario: setattr detected as reflection mutation
- **WHEN** a function contains `setattr(obj, "x", 1)`
- **THEN** a `ReflectionMutation` effect is emitted

### Requirement: control-flow and process effect detection
The detector SHALL emit `ProcessExit` for `sys.exit(...)`, `raise SystemExit`, and `os._exit(...)`; and SHALL additionally emit `ErrorSignal` for each of these (per the RAISE_RULE dual-emit: the exit semantics are given by `ProcessExit` while `ErrorSignal` is still emitted). The SystemExit family (`raise SystemExit`, `raise SystemExit(...)`, `sys.exit(...)`, `os._exit(...)`) emits `ProcessExit` + `ErrorSignal` and does NOT emit `ErrorReturn` — `ProcessExit` supplies the exit facet and `ErrorReturn` is therefore absent. `raise SystemExit` SHALL be `ProcessExit` (not `Panic`). The detector SHALL emit `RecoverBehavior` for a bare `except:` or an `except Exception` that swallows without re-raising. `assert False` SHALL NOT produce a `Panic` effect; `assert` is not an observable side effect in v1 and SHALL NOT produce any effect.

#### Scenario: sys.exit detected as ProcessExit and ErrorSignal
- **WHEN** a function contains `sys.exit(1)`
- **THEN** a `ProcessExit` effect is emitted and an `ErrorSignal` effect is emitted at the same location

#### Scenario: raise SystemExit detected as ProcessExit and ErrorSignal — ErrorReturn absent
- **WHEN** a function contains `raise SystemExit(0)`
- **THEN** the emitted effects are exactly {ProcessExit, ErrorSignal}; no `Panic` effect is emitted and no `ErrorReturn` effect is emitted

#### Scenario: assert is not an effect
- **WHEN** a function contains `assert False, "unreachable"`
- **THEN** no `Panic` effect and no other side effect is emitted for the assert statement

#### Scenario: swallowing except detected as RecoverBehavior
- **WHEN** a function contains `try: ... except Exception: pass`
- **THEN** a `RecoverBehavior` effect is emitted

### Requirement: concurrency effect detection
The detector SHALL emit `GoroutineSpawn` for `threading.Thread(...).start()`, `asyncio.create_task`, `loop.run_in_executor`, and `multiprocessing.Process.start`; `ChannelSend` for `queue.Queue.put`/`put_nowait` and `multiprocessing.Queue.put`; `MutexOp` for lock `acquire`/`release` and `with lock`; `WaitGroupOp` for `threading.Barrier` and `asyncio.gather`; `ContextCancellation` for raising/handling `asyncio.CancelledError` or calling `cancel()` on a task; and `SyncPoolOp` for `multiprocessing.Pool`.

#### Scenario: thread start detected
- **WHEN** a function contains `threading.Thread(target=f).start()`
- **THEN** a `GoroutineSpawn` effect is emitted

### Requirement: generator and async yield detection
The detector SHALL emit `GeneratorYield` for `yield`/`yield from` in a non-`async` function, and `AsyncGeneratorYield` for `yield` inside an `async def`.

#### Scenario: yield detected as GeneratorYield
- **WHEN** a non-async function contains `yield x`
- **THEN** a `GeneratorYield` effect is emitted

#### Scenario: yield in async function detected as AsyncGeneratorYield
- **WHEN** an `async def` contains `yield x`
- **THEN** an `AsyncGeneratorYield` effect is emitted

### Requirement: metaprogramming and descriptor detection
The detector SHALL emit `MetaprogrammingMutation` for `type(name, bases, dict)`, `types.new_class`, and `__class__ = ...`; and `DescriptorEffect` on the methods of a class that defines `__get__`, `__set__`, `__delete__`, or `__set_name__`.

#### Scenario: dynamic type creation detected
- **WHEN** a function contains `type("T", (), {})`
- **THEN** a `MetaprogrammingMutation` effect is emitted

#### Scenario: descriptor method detected
- **WHEN** a class defines `def __get__(self, obj, objtype=None): ...`
- **THEN** a `DescriptorEffect` effect is emitted on that method

### Requirement: resource management detection
The detector SHALL emit `ResourceManagement` for definitions of `__enter__`, `__exit__`, `__aenter__`, or `__aexit__`, and for functions decorated with `@contextmanager` or `@asynccontextmanager`.

#### Scenario: context manager method detected
- **WHEN** a class defines `def __enter__(self): ...` and `def __exit__(self, *a): ...`
- **THEN** a `ResourceManagement` effect is emitted on those methods

### Requirement: import side effect detection
The detector SHALL emit `ImportSideEffect` for `import`, `__import__`, or `importlib.import_module` that occurs inside a function body. Module-level imports SHALL NOT be attributed to a function and SHALL be skipped.

#### Scenario: function-level import detected
- **WHEN** a function body contains `importlib.import_module("os")`
- **THEN** an `ImportSideEffect` effect is emitted

#### Scenario: module-level import ignored
- **WHEN** a module has a top-level `import os`
- **THEN** no `ImportSideEffect` effect is attributed to any function

### Requirement: monkeypatch detection
The detector SHALL emit `MonkeyPatch` for `setattr(module, ...)` or `imported_name.attr = ...` where `imported_name` is an import alias or present in `sys.modules`.

#### Scenario: attribute assignment on imported module detected
- **WHEN** a function contains `other_module.foo = 1` where `other_module` is imported
- **THEN** a `MonkeyPatch` effect is emitted

### Requirement: database, log, time, and finalizer detection
The detector SHALL emit `DatabaseWrite` for `cursor.execute`/`executemany`/`commit` matched by name; `DatabaseTransaction` for `.commit`/`.rollback` on a conn/connection/session; `LogWrite` for `logging.*`, `logger.info`/`debug`/`warning`/`error`/`critical`/`exception`, and structlog calls; `TimeDependency` for `time.time`/`time.sleep`/`datetime.now`/`date.today`; and `FinalizerRegistration` for `atexit.register` and `weakref.finalize`.

#### Scenario: logging call detected
- **WHEN** a function contains `logging.info("x")`
- **THEN** a `LogWrite` effect is emitted

### Requirement: ambiguous constructs reported never dropped
The detector SHALL report ambiguous dynamic constructs rather than omitting them. The pure-builtin allowlist is explicitly enumerated (or references the gaze-py constant). A call to any name not on the allowlist and not matching a known effect pattern SHALL fall back to emitting `CallbackInvocation` with `detail={"confidence": "ambiguous"}` — it SHALL NOT be silently dropped. A statically-resolvable pure local call (a call to a locally-defined function with no observable effects) is NOT an effect and SHALL NOT produce a record. For `eval`, `exec`, and computed dynamic calls such as `getattr(obj, name)()`, the detector SHALL emit the most likely effect when a known pattern matches; otherwise it SHALL emit `CallbackInvocation` with `detail={"confidence": "ambiguous"}`.

#### Scenario: computed call reported as ambiguous callback
- **WHEN** a function contains `getattr(obj, name)()` with a computed attribute name and no matching pattern
- **THEN** a `CallbackInvocation` effect with `detail.confidence == "ambiguous"` is emitted

#### Scenario: unknown external call not silently dropped
- **WHEN** a function calls a name that is not on the pure-builtin allowlist and matches no known effect pattern
- **THEN** a `CallbackInvocation` effect with `detail.confidence == "ambiguous"` is emitted, not silently discarded

### Requirement: parse-error files skipped
The detector SHALL skip any file whose source raises `SyntaxError`, `ValueError`, `RecursionError` (raised during `ast.parse` or during AST traversal), `OSError` (e.g. `PermissionError` on read), or `MemoryError` (raised during AST traversal of a pathologically large structure), contributing no functions from that file. The broadened skip tuple is `(SyntaxError, ValueError, RecursionError, OSError, MemoryError)`. Analysis SHALL continue for all remaining files without raising. No `errors` array SHALL be added to any result. Each skipped file SHALL emit a diagnostic message to stderr; the diagnostic SHALL NOT appear in the stdout JSON-RPC result.

#### Scenario: syntax-error file skipped, valid file still analyzed
- **WHEN** `analyze_path` runs over a tree containing both `syntax_error.py` (invalid) and a valid module
- **THEN** the valid module's functions are returned and no exception is raised

#### Scenario: ValueError during parse skipped, remaining files returned
- **WHEN** `analyze_path` encounters a file that raises `ValueError` during `ast.parse` and another file is valid
- **THEN** the valid file's functions are returned, the erroneous file contributes no records, and no exception propagates

#### Scenario: RecursionError during traversal skipped, remaining files returned
- **WHEN** `analyze_path` encounters a pathologically nested file that triggers `RecursionError` during `ast.parse` or during AST traversal and another file is valid
- **THEN** the valid file's functions are returned, the erroneous file contributes no records, a diagnostic is written to stderr, and no exception propagates

#### Scenario: unreadable file (PermissionError) skipped, valid files still returned
- **WHEN** `analyze_path` encounters a file that raises `PermissionError` (an `OSError` subclass) on read and another file is valid
- **THEN** the valid file's functions are returned, the unreadable file contributes no records, a diagnostic is written to stderr, and no exception propagates

### Requirement: no fabricated effects for types without a Python analogue
The detector SHALL NOT emit `ChannelClose`, `DeferredReturnMutation`, `AtomicOp`, `CgoCall`, `Panic`, or `UnsafeMutation` unless a genuine Python rule matches. These types are retained in the `SideEffectType` enum as vocabulary for protocol compatibility, but the analyzer SHALL NOT fabricate them. Unused Go-only pattern lists lifted from gaze-py SHALL be deleted rather than retained as dead code.

#### Scenario: pure no-op function has no effects
- **WHEN** `analyze_source` analyzes `def noop():\n    pass\n`
- **THEN** the resulting record's `side_effects` is empty

#### Scenario: no-analogue types never appear in output
- **WHEN** any Python source is analyzed
- **THEN** no effect with `type` equal to `ChannelClose`, `DeferredReturnMutation`, `AtomicOp`, `CgoCall`, `Panic`, or `UnsafeMutation` is present in the output

### Requirement: Deterministic output ordering
The detector SHALL produce deterministic output. `functions[]` SHALL be ordered by `(file, line, name)`. `side_effects[]` within each function record SHALL be ordered by `(line, col, type)`. The analyzed file set is the ordered concatenation of the sorted `source_files` then `test_files`, de-duplicated preserving first occurrence (never a set union). The sentinel-exception collection is a deterministic ordered list, never a set. The same input tree MUST produce byte-identical JSON-RPC output across repeated invocations.

#### Scenario: two runs over the same fixture produce identical output
- **WHEN** `analyze_path` is invoked twice over the same fixture tree with the same arguments
- **THEN** the two resulting `list[FunctionRecord]` are identical in order and content, producing byte-identical serialized output

### Requirement: Package identity derivation
The `package` field of each `FunctionRecord` SHALL be derived by a single shared PACKAGE_DERIVATION helper: strip the `.py` extension from the file path relative to `root_path`, replace `/` with `.`, and drop a trailing `.__init__` (so `pkg/__init__.py` → `"pkg"`). This PACKAGE_DERIVATION helper is shared by the detector and complexity modules only — coverage result rows carry `file` + `function` (no `package`) per the protocol schema, so coverage does not use PACKAGE_DERIVATION. A separate FUNCTION_ENUMERATION helper (the per-function AST walk that maps line spans to function names) IS shared by all three modules including coverage, because coverage needs to map executed lines to the functions that contain them.

#### Scenario: pkg/__init__.py derives package as pkg
- **WHEN** `analyze_path` analyzes `pkg/__init__.py` under `root_path`
- **THEN** the resulting `FunctionRecord` entries have `package == "pkg"` (not `"pkg.__init__"`)

#### Scenario: nested module derives dotted package
- **WHEN** `analyze_path` analyzes `pkg/sub/mod.py` under `root_path`
- **THEN** the resulting `FunctionRecord` entries have `package == "pkg.sub.mod"`

### Requirement: Resource bounds on untrusted source
Analyzed source files are untrusted input. The detector SHALL read only **regular files**: it MUST `stat` each candidate path and skip any non-regular file (not `S_ISREG` — e.g. FIFOs, devices, sockets) with a stderr diagnostic before attempting `open()`. The byte-size cap `MAX_FILE_BYTES` (fixed constant = 16 MiB, mirroring the server's `MAX_LINE_CHARS` precedent) MUST be derived and enforced from the `stat` result (a PRE-`open()` guard): if `stat().st_size > MAX_FILE_BYTES` the file is skipped before `open()` is attempted, so a large or 0-byte-FIFO file cannot block `open()`. A second fixed constant `MAX_AST_DEPTH` (a fixed AST-depth/recursion budget) bounds traversal DURING the AST walk: the traversal uses a bounded `NodeVisitor` and catches `RecursionError` and `MemoryError` mid-traversal to skip-and-continue. It is infeasible to enforce AST depth before `ast.parse` is called, so the depth guard is applied during traversal, not before parse. Both `MAX_FILE_BYTES` and `MAX_AST_DEPTH` are fixed constants in v1 — they are NOT user-configurable. A file that exceeds either bound SHALL be skipped-and-continued exactly as a parse error is (see "parse-error files skipped"): the file contributes no function records, a per-file diagnostic is written to stderr, and analysis of the remaining files continues. The bounds MUST be enforced so that no single file can abort a whole request. This mirrors the server's `MAX_LINE_CHARS` posture established for protocol safety (Constitution V).

#### Scenario: over-cap file skipped, remaining files still returned
- **WHEN** `analyze_path` encounters a file whose byte size exceeds the configured cap, alongside a valid file
- **THEN** the over-cap file contributes no records, the valid file's functions are present in the result, a diagnostic is written to stderr, and no exception propagates

#### Scenario: pathologically nested file skipped, remaining files still returned
- **WHEN** `analyze_path` encounters a file with deeply nested AST structure that would exhaust the recursion budget, alongside a valid file
- **THEN** the pathological file contributes no records, the valid file's functions are present in the result, a diagnostic is written to stderr, and no exception propagates

#### Scenario: non-regular file (FIFO) skipped, valid files still returned
- **WHEN** `analyze_path` encounters a non-regular file (e.g. a FIFO named `x.py`) alongside a valid regular `.py` file
- **THEN** the non-regular file is skipped before `open()` is attempted, a stderr diagnostic is emitted, the valid file's functions are present in the result, and no exception propagates

### Requirement: gaze-py provenance retained
The lifted `detector.py` SHALL retain the gaze-py copyright header (Matt Peter, Apache 2.0) AND SHALL add an Apache-2.0 §4(b) change notice alongside it, for example: `# Modified 2026 by zero-dot-force: extended with Python-specific detection; Go-only pattern lists removed.` The detector SHALL NOT emit gaze-py internal effect identifiers (for example `se-XXXXXXXX`) in protocol JSON.

#### Scenario: provenance header present
- **WHEN** `src/snake_eyes/analysis/detector.py` is inspected
- **THEN** it contains the gaze-py Apache 2.0 provenance header

#### Scenario: Apache-2.0 change notice present
- **WHEN** `src/snake_eyes/analysis/detector.py` is inspected
- **THEN** it contains an Apache-2.0 §4(b) change notice identifying zero-dot-force as the modifier
