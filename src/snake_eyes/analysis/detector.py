# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: extended with Python-specific detection;
# Go-only pattern lists removed; adapted for mypy --strict and ruff;
# integrated with snake-eyes protocol models and shared helpers.
"""Python side-effect detector for snake-eyes.

Lifted from the gaze-py detector core and adapted for the snake-eyes protocol
(Gaze analyzer protocol v1.1.0).  Detects all SideEffectType values that have
a Python analogue, plus 10 new Python-specific types.

Public API:
- ``analyze_path(root_path, patterns) -> list[FunctionRecord]``
- ``analyze_source(source, filename, package) -> list[FunctionRecord]``
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Sequence
from typing import Any

from ._shared import (
    BROADENED_EXCEPTIONS,
    MAX_AST_DEPTH,
    derive_package,
    iter_source_files,
    ordered_file_list,
)
from .effects import SideEffectType
from .models import Effect, FunctionRecord

# ---------------------------------------------------------------------------
# Pure-builtin allowlist (D7 — statically-resolvable pure builtins are NOT
# effects and are NOT fallen through to CallbackInvocation).
# ---------------------------------------------------------------------------

_PURE_BUILTINS: frozenset[str] = frozenset(
    {
        "abs",
        "all",
        "any",
        "ascii",
        "bin",
        "bool",
        "breakpoint",
        "bytearray",
        "bytes",
        "callable",
        "chr",
        "compile",
        "complex",
        "delattr",
        "dict",
        "dir",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "globals",
        "hasattr",
        "hash",
        "hex",
        "id",
        # NOTE: "input" intentionally excluded — input() has a real stdin I/O effect.
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "locals",
        "map",
        "max",
        "memoryview",
        "min",
        "next",
        "object",
        "oct",
        "open",
        "ord",
        "pow",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "setattr",
        "slice",
        "sorted",
        "staticmethod",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "vars",
        "zip",
        # Python 3.x built-ins
        "classmethod",
        "property",
        "NotImplemented",
        "Ellipsis",
        "None",
        "True",
        "False",
        "__import__",
        "__name__",
        "__doc__",
        "__package__",
        "__spec__",
        "__loader__",
        "__builtins__",
    }
)

# Mutating method names for containers
_CONTAINER_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "append",
        "extend",
        "insert",
        "remove",
        "pop",
        "clear",
        "reverse",
        "sort",
        "add",
        "discard",
        "update",
        "difference_update",
        "intersection_update",
        "symmetric_difference_update",
    }
)


# Map/dict mutating methods (for MapMutation)
_MAP_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "update",
        "pop",
        "popitem",
        "clear",
        "setdefault",
    }
)

# Writer method names
_WRITER_METHODS: frozenset[str] = frozenset({"write", "writelines", "flush"})

# HTTP response names
_HTTP_RESPONSE_NAMES: frozenset[str] = frozenset(
    {"response", "make_response", "HttpResponse", "JSONResponse"}
)

# Logging method names
_LOG_METHODS: frozenset[str] = frozenset(
    {"debug", "info", "warning", "error", "critical", "exception", "log"}
)


# Lock/mutex method names
_MUTEX_METHODS: frozenset[str] = frozenset({"acquire", "release"})

# Queue put methods (ChannelSend)
_QUEUE_PUT_METHODS: frozenset[str] = frozenset({"put", "put_nowait"})

# db cursor method names
_DB_CURSOR_METHODS: frozenset[str] = frozenset(
    {"execute", "executemany", "executescript"}
)

# db commit/rollback (DatabaseTransaction)
_DB_TRANSACTION_METHODS: frozenset[str] = frozenset({"commit", "rollback"})

# Descriptor dunder methods
_DESCRIPTOR_METHODS: frozenset[str] = frozenset(
    {"__get__", "__set__", "__delete__", "__set_name__"}
)

# Resource management dunder methods
_RESOURCE_MGMT_METHODS: frozenset[str] = frozenset(
    {"__enter__", "__exit__", "__aenter__", "__aexit__"}
)

# SystemExit family: names that trigger ProcessExit + ErrorSignal (no ErrorReturn)
_SYSTEM_EXIT_NAMES: frozenset[str] = frozenset({"SystemExit"})

# Filesystem write mode chars
_WRITE_MODES: frozenset[str] = frozenset({"w", "a", "x", "+"})


def _loc(filename: str, node: ast.AST) -> str:
    """Format a location string ``"file.py:line:col"``."""
    line = getattr(node, "lineno", 0)
    col = getattr(node, "col_offset", 0)
    return f"{filename}:{line}:{col}"


def _effect(
    typ: SideEffectType,
    description: str,
    filename: str,
    node: ast.AST,
    target: str | None = None,
    detail: dict[str, Any] | None = None,
) -> Effect:
    return Effect(
        type=str(typ),
        description=description,
        location=_loc(filename, node),
        target=target,
        detail=detail,
    )


def _effect_sort_key(e: Effect) -> tuple[int, int, str]:
    """Sort key for effects: (line, col, type)."""
    if not e.location:
        return (0, 0, e.type)
    parts = e.location.split(":")
    line = int(parts[1]) if len(parts) > 1 else 0
    col = int(parts[2]) if len(parts) > 2 else 0
    return (line, col, e.type)


# ---------------------------------------------------------------------------
# Module-level sentinel scan (P0: SentinelError)
# ---------------------------------------------------------------------------


def _collect_sentinels(tree: ast.Module, filename: str) -> list[Effect]:
    """Collect SentinelError effects for module-level Exception subclasses."""
    effects: list[Effect] = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name: str | None = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr
            if base_name in ("Exception", "BaseException"):
                effects.append(
                    _effect(
                        SideEffectType.SentinelError,
                        f"Module defines sentinel exception class {node.name!r}",
                        filename,
                        node,
                        target=node.name,
                    )
                )
                break
    return effects


# ---------------------------------------------------------------------------
# Import alias tracking helpers
# ---------------------------------------------------------------------------


def _collect_import_aliases(tree: ast.Module) -> dict[str, str]:
    """Return a mapping of local name -> module (for top-level imports only).

    Used to recognise ``other_module.attr = ...`` as a MonkeyPatch.
    """
    aliases: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname if alias.asname else alias.name.split(".")[0]
                aliases[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                local = alias.asname if alias.asname else alias.name
                aliases[local] = f"{mod}.{alias.name}" if mod else alias.name
    return aliases


# ---------------------------------------------------------------------------
# Helper: is a call target a sys.exit / os._exit pattern?
# ---------------------------------------------------------------------------


def _is_sys_exit(node: ast.Call) -> bool:
    """Return True if *node* is sys.exit(...)."""
    fn = node.func
    return (
        isinstance(fn, ast.Attribute)
        and fn.attr == "exit"
        and isinstance(fn.value, ast.Name)
        and fn.value.id == "sys"
    )


def _is_os_exit(node: ast.Call) -> bool:
    """Return True if *node* is os._exit(...)."""
    fn = node.func
    return (
        isinstance(fn, ast.Attribute)
        and fn.attr == "_exit"
        and isinstance(fn.value, ast.Name)
        and fn.value.id == "os"
    )


def _is_system_exit_raise(exc_node: ast.expr | None) -> bool:
    """Return True if the raise target is SystemExit (name or call)."""
    if exc_node is None:
        return False
    if isinstance(exc_node, ast.Name) and exc_node.id in _SYSTEM_EXIT_NAMES:
        return True
    if (
        isinstance(exc_node, ast.Call)
        and isinstance(exc_node.func, ast.Name)
        and exc_node.func.id in _SYSTEM_EXIT_NAMES
    ):
        return True
    return False


# ---------------------------------------------------------------------------
# Helper: open() mode analysis
# ---------------------------------------------------------------------------


def _open_mode(call: ast.Call) -> str | None:
    """Extract the mode string from an ``open(...)`` call, or None."""
    # positional arg[1]
    if len(call.args) >= 2:
        arg = call.args[1]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    # keyword 'mode='
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


def _is_write_mode(mode: str) -> bool:
    return any(ch in mode for ch in _WRITE_MODES)


# ---------------------------------------------------------------------------
# Open-variable tracker: tracks names bound to open() call results
# ---------------------------------------------------------------------------


def _collect_open_vars(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, bool]:
    """Return a mapping of local variable name → is_write_mode for ``open()`` calls.

    The boolean value is True when the open() call uses a write-mode flag
    ('w', 'a', 'x', or '+'), False otherwise (e.g. 'r' or unknown mode).
    This is used to gate FileSystemWrite co-emission on write-mode opens only.
    """
    open_vars: dict[str, bool] = {}
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign):
            val = node.value
            if (
                isinstance(val, ast.Call)
                and isinstance(val.func, ast.Name)
                and val.func.id == "open"
            ):
                mode = _open_mode(val)
                is_write = mode is not None and _is_write_mode(mode)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        open_vars[target.id] = is_write
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            val = node.value
            if (
                isinstance(val, ast.Call)
                and isinstance(val.func, ast.Name)
                and val.func.id == "open"
            ):
                if isinstance(node.target, ast.Name):
                    mode = _open_mode(val)
                    is_write = mode is not None and _is_write_mode(mode)
                    open_vars[node.target.id] = is_write
    return open_vars


# ---------------------------------------------------------------------------
# Per-function effect detector
# ---------------------------------------------------------------------------


class _EffectVisitor(ast.NodeVisitor):
    """Collect side effects for a single function node."""

    def __init__(
        self,
        filename: str,
        import_aliases: dict[str, str],
        is_async: bool,
        global_names: set[str],
        nonlocal_names: set[str],
        param_names: set[str],
        open_vars: dict[str, bool],
        local_func_names: set[str],
        local_binding_names: set[str],
        module_func_names: set[str],
        enclosing_bindings: _BindingChain | None,
    ) -> None:
        self.filename = filename
        self.import_aliases = import_aliases
        self.is_async = is_async
        self.global_names = global_names
        self.nonlocal_names = nonlocal_names
        self.param_names = param_names
        self.open_vars = open_vars
        self.local_func_names = local_func_names
        self.local_binding_names = local_binding_names
        self.module_func_names = module_func_names
        self.enclosing_bindings = enclosing_bindings
        self.effects: list[Effect] = []
        self._depth = 0
        self._max_depth = MAX_AST_DEPTH

    def _check_depth(self) -> None:
        if self._depth > self._max_depth:
            raise RecursionError("AST depth budget exceeded in effect visitor")

    def generic_visit(self, node: ast.AST) -> None:
        self._depth += 1
        self._check_depth()
        super().generic_visit(node)
        self._depth -= 1

    def _add(
        self,
        typ: SideEffectType,
        description: str,
        node: ast.AST,
        target: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.effects.append(
            _effect(typ, description, self.filename, node, target, detail)
        )

    # -- ReturnValue ---------------------------------------------------------

    def visit_Return(self, node: ast.Return) -> None:
        self._add(
            SideEffectType.ReturnValue,
            "Function returns a value",
            node,
        )
        self.generic_visit(node)

    # -- Raise / ErrorSignal / ErrorReturn / ProcessExit ---------------------

    def visit_Raise(self, node: ast.Raise) -> None:
        exc = node.exc

        # SystemExit family: ProcessExit + ErrorSignal, NO ErrorReturn
        if _is_system_exit_raise(exc):
            self._add(SideEffectType.ProcessExit, "Process exit via SystemExit", node)
            self._add(SideEffectType.ErrorSignal, "Exception signal via raise", node)
            self.generic_visit(node)
            return

        # Bare raise (re-raise): ErrorReturn + ErrorSignal
        if exc is None:
            self._add(
                SideEffectType.ErrorReturn,
                "Function signals error via re-raise",
                node,
            )
            self._add(SideEffectType.ErrorSignal, "Exception signal via raise", node)
            self.generic_visit(node)
            return

        # raise Instance/Call/Name: ErrorReturn + ErrorSignal
        if isinstance(exc, (ast.Call, ast.Name, ast.Attribute)):
            exc_name: str | None = None
            if isinstance(exc, ast.Name):
                exc_name = exc.id
            elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                exc_name = exc.func.id
            elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Attribute):
                exc_name = exc.func.attr
            self._add(
                SideEffectType.ErrorReturn,
                "Function signals error via raise",
                node,
                target=exc_name,
            )
            self._add(SideEffectType.ErrorSignal, "Exception signal via raise", node)
            self.generic_visit(node)
            return

        # Fallback: still emit both
        self._add(
            SideEffectType.ErrorReturn,
            "Function signals error via raise",
            node,
        )
        self._add(SideEffectType.ErrorSignal, "Exception signal via raise", node)
        self.generic_visit(node)

    # -- Yield / AsyncGeneratorYield -----------------------------------------

    def visit_Yield(self, node: ast.Yield) -> None:
        if self.is_async:
            self._add(
                SideEffectType.AsyncGeneratorYield,
                "Async generator yields a value",
                node,
            )
        else:
            self._add(
                SideEffectType.GeneratorYield,
                "Generator yields a value",
                node,
            )
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        if self.is_async:
            self._add(
                SideEffectType.AsyncGeneratorYield,
                "Async generator yields from",
                node,
            )
        else:
            self._add(
                SideEffectType.GeneratorYield,
                "Generator yields from",
                node,
            )
        self.generic_visit(node)

    # -- Assignment: self.x / global / nonlocal / param mutations ------------

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._handle_assign_target(target, node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._handle_assign_target(node.target, node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._handle_assign_target(node.target, node)
        self.generic_visit(node)

    def _handle_assign_target(self, target: ast.expr, stmt: ast.AST) -> None:
        if isinstance(target, ast.Attribute):
            obj = target.value
            if isinstance(obj, ast.Name):
                if obj.id in ("self", "cls"):
                    self._add(
                        SideEffectType.ReceiverMutation,
                        f"Mutates receiver attribute {target.attr!r}",
                        stmt,
                        target=f"self.{target.attr}",
                    )
                    return
                if obj.id in self.import_aliases:
                    # MonkeyPatch: attribute assignment on an imported module alias
                    self._add(
                        SideEffectType.MonkeyPatch,
                        f"Monkeypatches {obj.id}.{target.attr}",
                        stmt,
                        target=f"{obj.id}.{target.attr}",
                    )
                    return
        elif isinstance(target, ast.Name):
            if target.id in self.global_names:
                self._add(
                    SideEffectType.GlobalMutation,
                    f"Mutates global variable {target.id!r}",
                    stmt,
                    target=target.id,
                )
                return
            if target.id in self.nonlocal_names:
                self._add(
                    SideEffectType.ClosureCaptureMutation,
                    f"Mutates nonlocal variable {target.id!r}",
                    stmt,
                    target=target.id,
                )
                return
        elif isinstance(target, ast.Subscript):
            obj = target.value
            if isinstance(obj, ast.Name):
                if obj.id in ("self", "cls"):
                    self._add(
                        SideEffectType.ReceiverMutation,
                        "Mutates receiver subscript",
                        stmt,
                        target="self[...]",
                    )
                elif obj.id in self.param_names:
                    self._add(
                        SideEffectType.PointerArgMutation,
                        f"Mutates parameter subscript {obj.id!r}",
                        stmt,
                        target=obj.id,
                    )
                elif obj.id in self.global_names:
                    self._add(
                        SideEffectType.GlobalMutation,
                        f"Mutates global subscript {obj.id!r}",
                        stmt,
                        target=obj.id,
                    )
                else:
                    # dict item assignment → MapMutation
                    self._add(
                        SideEffectType.MapMutation,
                        f"Mutates mapping subscript {obj.id!r}",
                        stmt,
                        target=obj.id,
                    )
            return
        # list slice assignment → SliceMutation
        if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Slice):
            self._add(
                SideEffectType.SliceMutation,
                "Mutates slice",
                stmt,
            )

    # -- Global / nonlocal declarations (just mark membership) ---------------

    def visit_Global(self, node: ast.Global) -> None:
        # Already tracked via global_names; no effect directly from the declaration.
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.generic_visit(node)

    # -- os.environ mutations ------------------------------------------------

    # -- Call expressions ----------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        self._handle_call(node)
        self.generic_visit(node)

    def _handle_call(self, node: ast.Call) -> None:  # noqa: C901 (complex)
        fn = node.func

        # sys.exit(...)
        if _is_sys_exit(node):
            self._add(SideEffectType.ProcessExit, "Process exit via sys.exit", node)
            self._add(SideEffectType.ErrorSignal, "Exception signal via sys.exit", node)
            return

        # os._exit(...)
        if _is_os_exit(node):
            self._add(SideEffectType.ProcessExit, "Process exit via os._exit", node)
            self._add(SideEffectType.ErrorSignal, "Exception signal via os._exit", node)
            return

        # print(...)
        if isinstance(fn, ast.Name) and fn.id == "print":
            # print(file=sys.stderr) → StderrWrite
            for kw in node.keywords:
                if kw.arg == "file" and isinstance(kw.value, ast.Attribute):
                    attr = kw.value
                    if (
                        isinstance(attr.value, ast.Name)
                        and attr.value.id == "sys"
                        and attr.attr == "stderr"
                    ):
                        self._add(
                            SideEffectType.StderrWrite,
                            "Writes to stderr via print",
                            node,
                        )
                        return
            self._add(SideEffectType.StdoutWrite, "Writes to stdout via print", node)
            return

        # eval(...) / exec(...)
        if isinstance(fn, ast.Name) and fn.id in ("eval", "exec"):
            self._add(
                SideEffectType.CallbackInvocation,
                f"Dynamic code execution via {fn.id}",
                node,
                detail={"confidence": "ambiguous"},
            )
            return

        # setattr(...)
        if isinstance(fn, ast.Name) and fn.id == "setattr":
            # setattr(module_alias, ...) → MonkeyPatch; else → ReflectionMutation
            if (
                len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in self.import_aliases
            ):
                self._add(
                    SideEffectType.MonkeyPatch,
                    "Monkeypatches module attribute via setattr",
                    node,
                    target=node.args[0].id,
                )
            else:
                self._add(
                    SideEffectType.ReflectionMutation,
                    "Mutates object attribute via setattr",
                    node,
                )
            return

        # delattr(...)
        if isinstance(fn, ast.Name) and fn.id == "delattr":
            self._add(
                SideEffectType.ReflectionMutation,
                "Deletes object attribute via delattr",
                node,
            )
            return

        # type("T", bases, dict) → MetaprogrammingMutation
        if isinstance(fn, ast.Name) and fn.id == "type" and len(node.args) == 3:
            self._add(
                SideEffectType.MetaprogrammingMutation,
                "Dynamic class creation via type()",
                node,
            )
            return

        # types.new_class(...)
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr == "new_class"
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "types"
        ):
            self._add(
                SideEffectType.MetaprogrammingMutation,
                "Dynamic class creation via types.new_class",
                node,
            )
            return

        # __import__(...)
        if isinstance(fn, ast.Name) and fn.id == "__import__":
            self._add(
                SideEffectType.ImportSideEffect,
                "Dynamic import via __import__",
                node,
            )
            return

        # importlib.import_module(...)
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr == "import_module"
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "importlib"
        ):
            self._add(
                SideEffectType.ImportSideEffect,
                "Dynamic import via importlib.import_module",
                node,
            )
            return

        # atexit.register(...)
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr == "register"
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "atexit"
        ):
            self._add(
                SideEffectType.FinalizerRegistration,
                "Finalizer registered via atexit.register",
                node,
            )
            return

        # weakref.finalize(...)
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr == "finalize"
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "weakref"
        ):
            self._add(
                SideEffectType.FinalizerRegistration,
                "Finalizer registered via weakref.finalize",
                node,
            )
            return

        # time.time() / time.sleep() / datetime.now() / date.today()
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
            obj_name = fn.value.id
            method_name = fn.attr
            if obj_name == "time" and method_name in (
                "time",
                "sleep",
                "monotonic",
                "perf_counter",
            ):
                self._add(
                    SideEffectType.TimeDependency,
                    f"Time dependency via {obj_name}.{method_name}",
                    node,
                )
                return
            if obj_name == "datetime" and method_name in ("now", "utcnow", "today"):
                self._add(
                    SideEffectType.TimeDependency,
                    f"Time dependency via {obj_name}.{method_name}",
                    node,
                )
                return
            if obj_name == "date" and method_name == "today":
                self._add(
                    SideEffectType.TimeDependency,
                    "Time dependency via date.today",
                    node,
                )
                return

        # logging.xxx(...)
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
            obj_name = fn.value.id
            method_name = fn.attr
            if obj_name == "logging" and method_name in _LOG_METHODS:
                self._add(
                    SideEffectType.LogWrite,
                    f"Log write via logging.{method_name}",
                    node,
                )
                return
            if obj_name in ("logger", "log") and method_name in _LOG_METHODS:
                self._add(
                    SideEffectType.LogWrite,
                    f"Log write via {obj_name}.{method_name}",
                    node,
                )
                return

        # asyncio.gather(...)
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr == "gather"
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "asyncio"
        ):
            self._add(
                SideEffectType.WaitGroupOp,
                "Wait group via asyncio.gather",
                node,
            )
            return

        # asyncio.create_task(...)
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr == "create_task"
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "asyncio"
        ):
            self._add(
                SideEffectType.GoroutineSpawn,
                "Async task spawn via asyncio.create_task",
                node,
            )
            return

        # loop.run_in_executor(...)
        if isinstance(fn, ast.Attribute) and fn.attr == "run_in_executor":
            self._add(
                SideEffectType.GoroutineSpawn,
                "Task spawn via loop.run_in_executor",
                node,
            )
            return

        # multiprocessing.Pool(...)
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr == "Pool"
            and isinstance(fn.value, ast.Name)
            and fn.value.id in ("multiprocessing", "mp")
        ):
            self._add(
                SideEffectType.SyncPoolOp,
                "Process pool via multiprocessing.Pool",
                node,
            )
            return

        # Method calls on objects
        if isinstance(fn, ast.Attribute):
            obj = fn.value
            method = fn.attr
            obj_name_str: str | None = None
            if isinstance(obj, ast.Name):
                obj_name_str = obj.id

            # sys.stdout.write / sys.stderr.write
            if isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name):
                if obj.value.id == "sys":
                    if obj.attr == "stdout" and method == "write":
                        self._add(
                            SideEffectType.StdoutWrite,
                            "Writes to stdout via sys.stdout.write",
                            node,
                        )
                        return
                    if obj.attr == "stderr" and method == "write":
                        self._add(
                            SideEffectType.StderrWrite,
                            "Writes to stderr via sys.stderr.write",
                            node,
                        )
                        return

            # os.environ mutations
            if isinstance(obj, ast.Attribute):
                inner = obj.value
                if (
                    isinstance(inner, ast.Name)
                    and inner.id == "os"
                    and obj.attr == "environ"
                    and method in ("update", "__setitem__")
                ):
                    self._add(
                        SideEffectType.EnvVarMutation,
                        "Mutates environment variable",
                        node,
                    )
                    return
            if obj_name_str == "os" and method == "putenv":
                self._add(
                    SideEffectType.EnvVarMutation,
                    "Mutates environment variable via os.putenv",
                    node,
                )
                return
            if obj_name_str == "environ" and method in ("update", "__setitem__"):
                self._add(
                    SideEffectType.EnvVarMutation,
                    "Mutates environment variable",
                    node,
                )
                return

            # os.remove / os.unlink / os.rmdir / os.chmod / ...
            if obj_name_str == "os" and method in (
                "remove",
                "unlink",
                "rmdir",
            ):
                self._add(
                    SideEffectType.FileSystemDelete,
                    f"Filesystem delete via os.{method}",
                    node,
                )
                return
            if obj_name_str == "os" and method in (
                "chmod",
                "chown",
                "rename",
                "mkdir",
                "makedirs",
                "symlink",
                "link",
            ):
                self._add(
                    SideEffectType.FileSystemMeta,
                    f"Filesystem metadata via os.{method}",
                    node,
                )
                return
            if obj_name_str == "os" and method == "write":
                self._add(
                    SideEffectType.FileSystemWrite,
                    "Filesystem write via os.write",
                    node,
                )
                return

            # shutil.copy* / shutil.rmtree
            if obj_name_str == "shutil":
                if method in ("copy", "copy2", "copyfile", "copytree", "move"):
                    self._add(
                        SideEffectType.FileSystemWrite,
                        f"Filesystem write via shutil.{method}",
                        node,
                    )
                    return
                if method == "rmtree":
                    self._add(
                        SideEffectType.FileSystemDelete,
                        "Filesystem delete via shutil.rmtree",
                        node,
                    )
                    return

            # Path.write_text / write_bytes / unlink / mkdir / rename / chmod
            if method == "write_text" or method == "write_bytes":
                self._add(
                    SideEffectType.FileSystemWrite,
                    f"Filesystem write via Path.{method}",
                    node,
                    target=obj_name_str,
                )
                return
            if method == "unlink":
                self._add(
                    SideEffectType.FileSystemDelete,
                    "Filesystem delete via Path.unlink",
                    node,
                    target=obj_name_str,
                )
                return
            if method in ("mkdir", "rename", "chmod"):
                self._add(
                    SideEffectType.FileSystemMeta,
                    f"Filesystem metadata via Path.{method}",
                    node,
                    target=obj_name_str,
                )
                return

            # threading.Thread(...).start()  — need to detect .start() on Thread obj
            if method == "start":
                # We can't fully prove this is a Thread, but .start() is characteristic
                self._add(
                    SideEffectType.GoroutineSpawn,
                    "Goroutine/thread spawn via .start()",
                    node,
                    target=obj_name_str,
                )
                return

            # Lock acquire/release
            if method in _MUTEX_METHODS:
                self._add(
                    SideEffectType.MutexOp,
                    f"Mutex operation via .{method}()",
                    node,
                    target=obj_name_str,
                )
                return

            # queue.put / put_nowait (ChannelSend)
            if method in _QUEUE_PUT_METHODS:
                self._add(
                    SideEffectType.ChannelSend,
                    f"Channel send via .{method}()",
                    node,
                    target=obj_name_str,
                )
                return

            # asyncio.CancelledError handling / task.cancel()
            if method == "cancel":
                self._add(
                    SideEffectType.ContextCancellation,
                    "Task cancellation via .cancel()",
                    node,
                    target=obj_name_str,
                )
                return

            # Barrier.wait → WaitGroupOp
            if method == "wait" and obj_name_str is not None:
                self._add(
                    SideEffectType.WaitGroupOp,
                    "Wait group synchronization via .wait()",
                    node,
                    target=obj_name_str,
                )
                return

            # DB cursor execute/executemany
            if method in _DB_CURSOR_METHODS:
                self._add(
                    SideEffectType.DatabaseWrite,
                    f"Database write via .{method}()",
                    node,
                    target=obj_name_str,
                )
                return

            # DB commit/rollback
            if method in _DB_TRANSACTION_METHODS:
                self._add(
                    SideEffectType.DatabaseTransaction,
                    f"Database transaction via .{method}()",
                    node,
                    target=obj_name_str,
                )
                return

            # HTTP response write
            if obj_name_str in _HTTP_RESPONSE_NAMES and method == "write":
                self._add(
                    SideEffectType.HTTPResponseWrite,
                    "HTTP response write",
                    node,
                    target=obj_name_str,
                )
                return

            # open(...) detected inline via open(...,'w') and .write
            # File write: .write / .writelines on a concretely-opened file
            # → StreamOutput; otherwise → WriterOutput (never double-emit)
            if method in _WRITER_METHODS:
                if obj_name_str is not None and obj_name_str in self.open_vars:
                    self._add(
                        SideEffectType.StreamOutput,
                        f"Stream output via {obj_name_str}.{method}()",
                        node,
                        target=obj_name_str,
                    )
                    # Co-emit FileSystemWrite only for write-mode opens (not 'r')
                    if self.open_vars[obj_name_str]:
                        self._add(
                            SideEffectType.FileSystemWrite,
                            f"Filesystem write via {obj_name_str}.{method}()",
                            node,
                            target=obj_name_str,
                        )
                else:
                    # Parameter or unknown-origin file object
                    self._add(
                        SideEffectType.WriterOutput,
                        f"Writer output via .{method}()",
                        node,
                        target=obj_name_str,
                    )
                return

            # Container mutating methods (with self.x and param precedence)
            if method in _CONTAINER_MUTATING_METHODS:
                # Check chained: self.attr.method() → obj is Attribute(Name('self'),...)
                _obj_root: str | None = None
                if isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name):
                    _obj_root = obj.value.id
                if obj_name_str in ("self", "cls") or _obj_root in ("self", "cls"):
                    self._add(
                        SideEffectType.ReceiverMutation,
                        f"Mutates receiver via self.{method}()",
                        node,
                        target=f"self.{method}",
                    )
                elif obj_name_str is not None and obj_name_str in self.param_names:
                    self._add(
                        SideEffectType.PointerArgMutation,
                        f"Mutates parameter {obj_name_str!r} via .{method}()",
                        node,
                        target=obj_name_str,
                    )
                else:
                    self._add(
                        SideEffectType.ContainerMutation,
                        f"Container mutation via .{method}()",
                        node,
                        target=obj_name_str,
                    )
                return

            # Map mutating methods
            if method in _MAP_MUTATING_METHODS:
                if obj_name_str is not None and obj_name_str in self.param_names:
                    self._add(
                        SideEffectType.PointerArgMutation,
                        f"Mutates parameter {obj_name_str!r} via .{method}()",
                        node,
                        target=obj_name_str,
                    )
                else:
                    self._add(
                        SideEffectType.MapMutation,
                        f"Map mutation via .{method}()",
                        node,
                        target=obj_name_str,
                    )
                return

            # Unknown attribute call on object → ambiguous if not a known safe method
            # Check if it's a call on an imported module attribute
            if obj_name_str is not None and obj_name_str in self.import_aliases:
                # Module-level call on an import — could be anything, treat as ambiguous
                # But skip if it's an obviously known module operation we haven't caught
                pass

            # Log methods on a logger-like object (variable named logger/log)
            if obj_name_str in ("logger", "log") and method in _LOG_METHODS:
                self._add(
                    SideEffectType.LogWrite,
                    f"Log write via {obj_name_str}.{method}",
                    node,
                )
                return

        # open(..., 'w') standalone call (not already consumed above)
        if isinstance(fn, ast.Name) and fn.id == "open":
            mode = _open_mode(node)
            if mode is not None and _is_write_mode(mode):
                self._add(
                    SideEffectType.FileSystemWrite,
                    f"Filesystem write via open(..., {mode!r})",
                    node,
                )
            return

        # computed getattr(obj, name)() call
        if (
            isinstance(fn, ast.Call)
            and isinstance(fn.func, ast.Name)
            and fn.func.id == "getattr"
        ):
            self._add(
                SideEffectType.CallbackInvocation,
                "Computed attribute call via getattr",
                node,
                detail={"confidence": "ambiguous"},
            )
            return

        # Name-call fallback resolves pure builtins, direct local definitions,
        # then guarded module definitions. Imports and naming conventions do not
        # prove purity, so unresolved names remain ambiguous.
        if isinstance(fn, ast.Name):
            name = fn.id
            if name in _PURE_BUILTINS:
                return  # pure builtin, no effect
            if name in self.local_func_names:
                return  # directly resolved local definition
            module_resolved = (
                name in self.module_func_names
                and name not in self.local_binding_names
                and name not in self.nonlocal_names
                and (
                    name in self.global_names
                    or self.enclosing_bindings is None
                    or name not in self.enclosing_bindings
                )
            )
            if module_resolved:
                return  # statically-resolvable pure local call is NOT an effect
            # Unknown external call → CallbackInvocation ambiguous
            self._add(
                SideEffectType.CallbackInvocation,
                f"Ambiguous call to {name!r}",
                node,
                detail={"confidence": "ambiguous"},
            )

    # -- Subscript assignments to os.environ ---------------------------------

    def visit_Subscript(self, node: ast.Subscript) -> None:
        # Handled via visit_Assign for assignment context.
        self.generic_visit(node)

    # -- except / RecoverBehavior --------------------------------------------

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Check if the handler swallows without re-raising
        has_reraise = any(
            isinstance(stmt, ast.Raise) and stmt.exc is None
            for stmt in ast.walk(node)
            if isinstance(stmt, ast.Raise)
        )
        # bare except: or except Exception: with no re-raise
        if not has_reraise:
            exc_type = node.type
            if exc_type is None:  # bare except:
                self._add(
                    SideEffectType.RecoverBehavior,
                    "Bare except swallows exception",
                    node,
                )
            elif isinstance(exc_type, ast.Name) and exc_type.id == "Exception":
                self._add(
                    SideEffectType.RecoverBehavior,
                    "Broad except Exception swallows exception",
                    node,
                )
        self.generic_visit(node)

    # -- Import statements inside functions (ImportSideEffect) ---------------

    def visit_Import(self, node: ast.Import) -> None:
        self._add(
            SideEffectType.ImportSideEffect,
            "Function-level import",
            node,
        )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._add(
            SideEffectType.ImportSideEffect,
            "Function-level import from",
            node,
        )
        self.generic_visit(node)

    # -- __dict__ assignment -------------------------------------------------

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # __dict__ assignment: handled through visit_Assign
        self.generic_visit(node)

    # -- Contextmanager decorator / ResourceManagement -----------------------
    # Handled at the function-record level in _analyze_func_node.

    # -- os.environ[...] = ... handled via visit_Assign ----------------------

    # -- Do NOT descend into nested FunctionDef / AsyncFunctionDef
    # Effects of nested functions are collected by a separate _EffectVisitor.

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        pass  # nested — analyzed separately

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        pass  # nested — analyzed separately

    # -- Assert: NOT an effect (spec: assert is not an effect in v1) ---------

    def visit_Assert(self, node: ast.Assert) -> None:
        pass  # intentionally skip


# ---------------------------------------------------------------------------
# Env-var subscript assignment detection (os.environ[...] = ...)
# ---------------------------------------------------------------------------


def _is_environ_subscript(target: ast.expr) -> bool:
    """Return True if the target is os.environ[...] or environ[...]."""
    if not isinstance(target, ast.Subscript):
        return False
    obj = target.value
    if isinstance(obj, ast.Attribute):
        return (
            isinstance(obj.value, ast.Name)
            and obj.value.id == "os"
            and obj.attr == "environ"
        )
    if isinstance(obj, ast.Name):
        return obj.id == "environ"
    return False


# ---------------------------------------------------------------------------
# Descriptor / resource-mgmt class-level inspection
# ---------------------------------------------------------------------------


def _class_has_descriptor_method(class_node: ast.ClassDef) -> bool:
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name in _DESCRIPTOR_METHODS:
                return True
    return False


def _class_has_resource_mgmt_method(class_node: ast.ClassDef) -> bool:
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name in _RESOURCE_MGMT_METHODS:
                return True
    return False


def _has_contextmanager_decorator(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id in (
            "contextmanager",
            "asynccontextmanager",
        ):
            return True
        if isinstance(dec, ast.Attribute) and dec.attr in (
            "contextmanager",
            "asynccontextmanager",
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Param extraction
# ---------------------------------------------------------------------------


def _collect_params(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = func_node.args
    params: set[str] = set()
    for arg in (
        args.args
        + args.posonlyargs
        + args.kwonlyargs
        + ([args.vararg] if args.vararg else [])
        + ([args.kwarg] if args.kwarg else [])
    ):
        params.add(arg.arg)
    return params


def _collect_lambda_params(node: ast.Lambda) -> set[str]:
    args = node.args
    return {
        argument.arg
        for argument in (
            *args.posonlyargs,
            *args.args,
            *args.kwonlyargs,
            *((args.vararg,) if args.vararg else ()),
            *((args.kwarg,) if args.kwarg else ()),
        )
    }


class _ScopeBindingCollector(ast.NodeVisitor):
    """Collect binders in one Python lexical scope without entering child scopes."""

    _MAX_ALIAS_TARGETS = 64

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.classes: dict[str, ast.ClassDef] = {}
        self.constructor_mutations: set[str] = set()
        self.global_rebindings: set[str] = set()
        self.deleted_names: set[str] = set()
        self.aliases: dict[str, str] = {}
        self.alias_targets: dict[str, set[str]] = {}
        self.unknown_alias_mutation = False
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()
        self._conditional_depth = 0
        self._depth = 0

    def visit(self, node: ast.AST) -> Any:
        self._depth += 1
        if self._depth > MAX_AST_DEPTH:
            self._depth -= 1
            raise RecursionError("AST depth budget exceeded in scope binding collector")
        try:
            return super().visit(node)
        finally:
            self._depth -= 1

    def _bind(self, name: str) -> None:
        self.counts[name] = self.counts.get(name, 0) + 1

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._bind(node.id)
        if isinstance(node.ctx, ast.Del):
            self.deleted_names.add(node.id)
            self.aliases.pop(node.id, None)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if self._conditional_depth == 0:
                    self.aliases.pop(target.id, None)
                    self.alias_targets.pop(target.id, None)
        if isinstance(node.value, ast.Name):
            sources = self._alias_sources(node.value.id)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if self._conditional_depth:
                        targets = self.alias_targets.setdefault(target.id, {target.id})
                        if len(targets) + len(sources) > self._MAX_ALIAS_TARGETS:
                            self.unknown_alias_mutation = True
                        else:
                            targets.update(sources)
                    else:
                        source = _resolve_alias(node.value.id, self.aliases)
                        self.aliases[target.id] = source
                        self.alias_targets[target.id] = set(sources)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.generic_visit(node)
        if isinstance(node.target, ast.Name):
            self.aliases.pop(node.target.id, None)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and node.value is not None:
            self.aliases.pop(node.target.id, None)
            if isinstance(node.value, ast.Name):
                source = _resolve_alias(node.value.id, self.aliases)
                self.aliases[node.target.id] = source
                self.alias_targets[node.target.id] = set(
                    self._alias_sources(node.value.id)
                )

    def _alias_sources(self, name: str) -> set[str]:
        sources = self.alias_targets.get(name)
        if sources is None:
            return {_resolve_alias(name, self.aliases)}
        return sources

    def _visit_conditional(self, node: ast.AST) -> None:
        self._conditional_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self._conditional_depth -= 1

    visit_If = _visit_conditional
    visit_For = _visit_conditional
    visit_AsyncFor = _visit_conditional
    visit_While = _visit_conditional
    visit_Try = _visit_conditional
    visit_TryStar = _visit_conditional
    visit_With = _visit_conditional
    visit_AsyncWith = _visit_conditional
    visit_Match = _visit_conditional

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._bind(node.name)
        self.functions[node.name] = node
        self._visit_function_header(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._bind(node.name)
        self.functions[node.name] = node
        self._visit_function_header(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._bind(node.name)
        self.classes[node.name] = node
        for expression in (*node.decorator_list, *node.bases):
            self.visit(expression)
        for keyword in node.keywords:
            self.visit(keyword.value)
        for type_param in getattr(node, "type_params", ()):
            self.visit(type_param)
        statement_results: list[tuple[ast.stmt, _ScopeBindingCollector]] = []
        class_globals: set[str] = set()
        for statement in node.body:
            collector = _ScopeBindingCollector()
            collector.visit(statement)
            statement_results.append((statement, collector))
            class_globals.update(collector.global_names)
        class_names: set[str] = set()
        class_aliases: dict[str, set[str]] = {}
        for statement, collector in statement_results:
            self.unknown_alias_mutation |= collector.unknown_alias_mutation
            for name in collector.constructor_mutations:
                if name in class_names and name not in class_aliases:
                    continue
                for source in class_aliases.get(name, {name}):
                    self.constructor_mutations.update(self._alias_sources(source))
            self.global_rebindings.update(class_globals & set(collector.counts))
            if isinstance(statement, ast.Delete):
                class_names.difference_update(collector.deleted_names)
                for name in collector.deleted_names:
                    class_aliases.pop(name, None)
                continue
            if isinstance(
                statement,
                (
                    ast.Assign,
                    ast.AugAssign,
                    ast.Import,
                    ast.ImportFrom,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                class_names.update(collector.counts)
                for name in collector.counts:
                    class_aliases.pop(name, None)
                for alias in collector.aliases:
                    sources: set[str] = set()
                    for source in collector._alias_sources(alias):
                        sources.update(class_aliases.get(source, {source}))
                    class_aliases[alias] = sources
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                class_names.update(collector.counts)
                for name in collector.counts:
                    class_aliases.pop(name, None)
                for alias in collector.aliases:
                    sources = set()
                    for source in collector._alias_sources(alias):
                        sources.update(class_aliases.get(source, {source}))
                    class_aliases[alias] = sources

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_arguments(node.args)
        local_names = _collect_lambda_params(node)
        collector = _ScopeBindingCollector()
        collector.visit(node.body)
        self.unknown_alias_mutation |= collector.unknown_alias_mutation
        local_names.update(collector.counts)
        self.constructor_mutations.update(
            name for name in collector.constructor_mutations if name not in local_names
        )

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in {"setattr", "delattr"}
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in {"__init__", "__new__"}
        ):
            self.constructor_mutations.update(self._alias_sources(node.args[0].id))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            isinstance(node.ctx, (ast.Store, ast.Del))
            and node.attr in {"__init__", "__new__"}
            and isinstance(node.value, ast.Name)
        ):
            self.constructor_mutations.update(self._alias_sources(node.value.id))
        self.generic_visit(node)

    def _visit_function_header(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._visit_arguments(node.args)
        if node.returns is not None:
            self.visit(node.returns)
        for type_param in getattr(node, "type_params", ()):
            self.visit(type_param)

    def _visit_arguments(self, arguments: ast.arguments) -> None:
        for default in (*arguments.defaults, *arguments.kw_defaults):
            if default is not None:
                self.visit(default)
        all_arguments = (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
        annotations = [argument.annotation for argument in all_arguments]
        annotations.extend(
            argument.annotation
            for argument in (arguments.vararg, arguments.kwarg)
            if argument is not None
        )
        for annotation in annotations:
            if annotation is not None:
                self.visit(annotation)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        # Comprehension targets live in an implicit child scope. Walrus
        # expressions in their iterables and filters bind in this scope.
        self.visit(node.iter)
        for condition in node.ifs:
            self.visit(condition)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._bind(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self._bind(alias.asname or alias.name)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self._bind(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name is not None:
            self._bind(node.name)
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name is not None:
            self._bind(node.name)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest is not None:
            self._bind(node.rest)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)
        for name in node.names:
            self._bind(name)


class _BindingChain:
    """Persistent lexical-binding chain that avoids cumulative set copies."""

    def __init__(self, names: set[str], parent: _BindingChain | None = None) -> None:
        self.names = names
        self.parent = parent

    def __contains__(self, name: str) -> bool:
        scope: _BindingChain | None = self
        while scope is not None:
            if name in scope.names:
                return True
            scope = scope.parent
        return False


class _ShadowedNames:
    """Membership view over local, module, and enclosing bindings without copies."""

    def __init__(
        self,
        local: set[str],
        module: set[str] | None,
        enclosing: _BindingChain | None,
        global_names: set[str] | None = None,
    ) -> None:
        self.local = local
        self.module = module
        self.enclosing = enclosing
        self.global_names = global_names or set()

    def __contains__(self, name: str) -> bool:
        if name in self.global_names:
            return self.module is not None and name in self.module
        return (
            name in self.local
            or (self.module is not None and name in self.module)
            or (self.enclosing is not None and name in self.enclosing)
        )


def _collect_scope_bindings(
    scope: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> _ScopeBindingCollector:
    collector = _ScopeBindingCollector()
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for parameter in _collect_params(scope):
            collector._bind(parameter)
    for statement in scope.body:
        collector.visit(statement)
    return collector


def _resolve_alias(name: str, aliases: dict[str, str]) -> str:
    """Resolve a direct-name alias chain without looping on cycles."""
    seen: set[str] = set()
    while name in aliases and name not in seen:
        seen.add(name)
        name = aliases[name]
    return name


def _collect_module_invalidations(
    tree: ast.Module,
) -> tuple[set[str], set[str], bool]:
    """Return replacement, constructor-mutation, and broad invalidations."""
    invalidated: set[str] = set()
    constructor_invalidated: set[str] = set()
    wildcard_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == "*" for alias in node.names
        ):
            wildcard_import = True
        elif isinstance(node, ast.Module):
            bindings = _collect_scope_bindings(node)
            invalidated.update(bindings.global_rebindings)
            constructor_invalidated.update(bindings.constructor_mutations)
            wildcard_import |= bindings.unknown_alias_mutation
            constructor_invalidated.update(
                _resolve_alias(source, bindings.aliases)
                for alias, source in bindings.aliases.items()
                if alias in bindings.constructor_mutations
            )

    def visit_scopes(nodes: Sequence[ast.AST], enclosing: _BindingChain | None) -> None:
        nonlocal wildcard_import
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bindings = _collect_scope_bindings(node)
                wildcard_import |= bindings.unknown_alias_mutation
                bound_names = set(bindings.counts)
                invalidated.update(bindings.global_names & bound_names)
                invalidated.update(bindings.global_rebindings)
                for name in bindings.constructor_mutations:
                    if name in bindings.global_names or (
                        name not in bound_names
                        and name not in bindings.nonlocal_names
                        and (enclosing is None or name not in enclosing)
                    ):
                        constructor_invalidated.add(name)
                for alias in bindings.constructor_mutations & bindings.aliases.keys():
                    source = _resolve_alias(alias, bindings.aliases)
                    if source not in bound_names and (
                        enclosing is None or source not in enclosing
                    ):
                        constructor_invalidated.add(source)
                closure_names = bound_names - bindings.global_names
                visit_scopes(node.body, _BindingChain(closure_names, enclosing))
            elif isinstance(node, ast.ClassDef):
                # Class namespaces are not enclosing lexical scopes for methods.
                visit_scopes(node.body, enclosing)
            else:
                visit_scopes(list(ast.iter_child_nodes(node)), enclosing)

    visit_scopes(list(tree.body), None)
    return invalidated, constructor_invalidated, wildcard_import


def _is_trivial_class(
    node: ast.ClassDef, shadowed_names: set[str] | _BindingChain | _ShadowedNames
) -> bool:
    """Return whether constructing *node* cannot invoke user-defined code."""
    safe_exception_base = (
        len(node.bases) == 1
        and isinstance(node.bases[0], ast.Name)
        and node.bases[0].id in {"BaseException", "Exception"}
        and node.bases[0].id not in shadowed_names
    )
    return (
        (not node.bases or safe_exception_base)
        and not node.keywords
        and not node.decorator_list
        and all(isinstance(statement, ast.Pass) for statement in node.body)
    )


# ---------------------------------------------------------------------------
# Analyze a single function node
# ---------------------------------------------------------------------------


def _analyze_func_node(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    filename: str,
    is_async: bool,
    import_aliases: dict[str, str],
    is_descriptor_class: bool,
    is_resource_mgmt: bool,
    module_func_names: set[str] | None = None,
    module_binding_names: set[str] | None = None,
    enclosing_bindings: _BindingChain | None = None,
) -> FunctionRecord:
    """Produce a FunctionRecord for a single def/async def node."""
    param_names = _collect_params(func_node)
    scope_bindings = _collect_scope_bindings(func_node)
    global_names = scope_bindings.global_names
    nonlocal_names = scope_bindings.nonlocal_names
    open_vars = _collect_open_vars(func_node)
    # Collect names of locally-defined functions and classes visible in this scope:
    # nested functions/classes defined directly inside this function, plus all
    # module-level function/class names (passed by the caller from the module tree).
    # Calls to any of these are statically-resolvable pure local calls or class
    # constructors and are NOT effects.
    bound_names = set(scope_bindings.counts)
    direct_definitions = {
        id(statement)
        for statement in func_node.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    resolved_local_names = {
        name
        for name, function_node in scope_bindings.functions.items()
        if scope_bindings.counts[name] == 1 and id(function_node) in direct_definitions
    }
    class_base_shadows = _ShadowedNames(
        bound_names,
        module_binding_names,
        enclosing_bindings,
        global_names,
    )
    resolved_local_names.update(
        name
        for name, class_node in scope_bindings.classes.items()
        if scope_bindings.counts[name] == 1
        and id(class_node) in direct_definitions
        and not scope_bindings.unknown_alias_mutation
        and name not in scope_bindings.constructor_mutations
        and _is_trivial_class(class_node, class_base_shadows)
    )
    local_func_names = resolved_local_names
    local_binding_names = bound_names - resolved_local_names

    # Collect os.environ subscript assignments at the stmt level
    env_mutation_nodes: list[ast.AST] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if _is_environ_subscript(tgt):
                    env_mutation_nodes.append(node)
        elif isinstance(node, ast.AugAssign):
            if _is_environ_subscript(node.target):
                env_mutation_nodes.append(node)

    visitor = _EffectVisitor(
        filename=filename,
        import_aliases=import_aliases,
        is_async=is_async,
        global_names=global_names,
        nonlocal_names=nonlocal_names,
        param_names=param_names,
        open_vars=open_vars,
        local_func_names=local_func_names,
        local_binding_names=local_binding_names,
        module_func_names=module_func_names or set(),
        enclosing_bindings=enclosing_bindings,
    )

    # Only visit direct children of the function body (not nested function bodies)
    for stmt in ast.iter_child_nodes(func_node):
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            try:
                visitor.visit(stmt)
            except BROADENED_EXCEPTIONS:
                pass

    effects = list(visitor.effects)

    # env-mutation nodes (subscript assign to os.environ)
    for env_node in env_mutation_nodes:
        effects.append(
            _effect(
                SideEffectType.EnvVarMutation,
                "Mutates environment variable via os.environ[...]",
                filename,
                env_node,
            )
        )

    # Descriptor method: if the function is a descriptor method in a descriptor class
    if func_node.name in _DESCRIPTOR_METHODS and is_descriptor_class:
        effects.append(
            _effect(
                SideEffectType.DescriptorEffect,
                f"Descriptor protocol method {func_node.name!r}",
                filename,
                func_node,
            )
        )

    # Resource management: __enter__/__exit__ or @contextmanager
    if func_node.name in _RESOURCE_MGMT_METHODS and is_resource_mgmt:
        effects.append(
            _effect(
                SideEffectType.ResourceManagement,
                f"Resource management method {func_node.name!r}",
                filename,
                func_node,
            )
        )
    if _has_contextmanager_decorator(func_node):
        effects.append(
            _effect(
                SideEffectType.ResourceManagement,
                "Resource management via @contextmanager decorator",
                filename,
                func_node,
            )
        )

    # sentinel effects: attached to first function record or omitted if no functions.

    # Sort effects by (line, col, type)
    effects.sort(key=_effect_sort_key)

    return FunctionRecord(
        name=func_node.name,
        package="",  # filled by caller
        file=filename,
        line=func_node.lineno,
        side_effects=tuple(effects),
    )


# ---------------------------------------------------------------------------
# Module-level walker: enumerate all def/async def recursively
# ---------------------------------------------------------------------------


def _walk_class_for_funcs(
    class_node: ast.ClassDef,
    filename: str,
    import_aliases: dict[str, str],
    is_descriptor: bool,
    is_resource_mgmt: bool,
    module_func_names: set[str] | None = None,
    module_binding_names: set[str] | None = None,
    enclosing_bindings: _BindingChain | None = None,
) -> list[FunctionRecord]:
    """Collect FunctionRecords for methods of a class node."""
    records: list[FunctionRecord] = []
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef):
            rec = _analyze_func_node(
                item,
                filename,
                False,
                import_aliases,
                is_descriptor,
                is_resource_mgmt,
                module_func_names,
                module_binding_names,
                enclosing_bindings,
            )
            records.append(rec)
            # Recurse into nested classes / functions inside method
            records.extend(
                _walk_module_body(
                    list(ast.iter_child_nodes(item)),
                    filename,
                    import_aliases,
                    module_func_names,
                    module_binding_names,
                    _BindingChain(
                        set(_collect_scope_bindings(item).counts), enclosing_bindings
                    ),
                )
            )
        elif isinstance(item, ast.AsyncFunctionDef):
            rec = _analyze_func_node(
                item,
                filename,
                True,
                import_aliases,
                is_descriptor,
                is_resource_mgmt,
                module_func_names,
                module_binding_names,
                enclosing_bindings,
            )
            records.append(rec)
            records.extend(
                _walk_module_body(
                    list(ast.iter_child_nodes(item)),
                    filename,
                    import_aliases,
                    module_func_names,
                    module_binding_names,
                    _BindingChain(
                        set(_collect_scope_bindings(item).counts), enclosing_bindings
                    ),
                )
            )
        elif isinstance(item, ast.ClassDef):
            # Nested class
            sub_is_descriptor = _class_has_descriptor_method(item)
            sub_is_resource = _class_has_resource_mgmt_method(item)
            records.extend(
                _walk_class_for_funcs(
                    item,
                    filename,
                    import_aliases,
                    sub_is_descriptor,
                    sub_is_resource,
                    module_func_names,
                    module_binding_names,
                    enclosing_bindings,
                )
            )
    return records


def _walk_module_body(
    nodes: list[ast.AST],
    filename: str,
    import_aliases: dict[str, str],
    module_func_names: set[str] | None = None,
    module_binding_names: set[str] | None = None,
    enclosing_bindings: _BindingChain | None = None,
) -> list[FunctionRecord]:
    """Recursively collect FunctionRecords from a list of AST nodes."""
    records: list[FunctionRecord] = []
    for node in nodes:
        if isinstance(node, ast.FunctionDef):
            rec = _analyze_func_node(
                node,
                filename,
                False,
                import_aliases,
                False,
                False,
                module_func_names,
                module_binding_names,
                enclosing_bindings,
            )
            records.append(rec)
            # Recurse into nested defs/classes inside this function
            records.extend(
                _walk_module_body(
                    list(ast.iter_child_nodes(node)),
                    filename,
                    import_aliases,
                    module_func_names,
                    module_binding_names,
                    _BindingChain(
                        set(_collect_scope_bindings(node).counts), enclosing_bindings
                    ),
                )
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            rec = _analyze_func_node(
                node,
                filename,
                True,
                import_aliases,
                False,
                False,
                module_func_names,
                module_binding_names,
                enclosing_bindings,
            )
            records.append(rec)
            records.extend(
                _walk_module_body(
                    list(ast.iter_child_nodes(node)),
                    filename,
                    import_aliases,
                    module_func_names,
                    module_binding_names,
                    _BindingChain(
                        set(_collect_scope_bindings(node).counts), enclosing_bindings
                    ),
                )
            )
        elif isinstance(node, ast.ClassDef):
            is_descriptor = _class_has_descriptor_method(node)
            is_resource = _class_has_resource_mgmt_method(node)
            records.extend(
                _walk_class_for_funcs(
                    node,
                    filename,
                    import_aliases,
                    is_descriptor,
                    is_resource,
                    module_func_names,
                    module_binding_names,
                    enclosing_bindings,
                )
            )
    return records


def _analyze_tree(
    tree: ast.Module,
    filename: str,
    package: str,
) -> list[FunctionRecord]:
    """Produce FunctionRecords from a parsed AST module."""
    import_aliases = _collect_import_aliases(tree)
    sentinel_effects = _collect_sentinels(tree, filename)
    module_bindings = _collect_scope_bindings(tree)
    bound_names = set(module_bindings.counts)
    invalidated_names, constructor_invalidations, wildcard_import = (
        _collect_module_invalidations(tree)
    )
    direct_definitions = {
        id(statement)
        for statement in tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    # Collect all function and class names defined at module level so that calls
    # to them are not treated as ambiguous (NEVER_DROP carve-out for pure local
    # calls and class constructors).
    module_func_names = {
        name
        for name, function_node in module_bindings.functions.items()
        if module_bindings.counts[name] == 1
        and id(function_node) in direct_definitions
        and name not in invalidated_names
    }
    module_func_names.update(
        name
        for name, class_node in module_bindings.classes.items()
        if module_bindings.counts[name] == 1
        and id(class_node) in direct_definitions
        and name not in invalidated_names
        and name not in constructor_invalidations
        and not wildcard_import
        and _is_trivial_class(class_node, bound_names)
    )

    raw_records = _walk_module_body(
        list(ast.iter_child_nodes(tree)),
        filename,
        import_aliases,
        module_func_names,
        bound_names,
        None,
    )

    # Attach sentinel effects to the first function record in the module.

    # Attach sentinels to the first record or as a standalone record
    if sentinel_effects:
        if raw_records:
            first = raw_records[0]
            combined_effects = list(first.side_effects) + sentinel_effects
            combined_effects.sort(key=_effect_sort_key)
            raw_records[0] = FunctionRecord(
                name=first.name,
                package=package,
                file=first.file,
                line=first.line,
                side_effects=tuple(combined_effects),
            )
        # else: no functions, sentinel has nowhere to go — that's intentional

    # Fill in package for all records
    filled: list[FunctionRecord] = []
    for rec in raw_records:
        if rec.package == "":
            filled.append(
                FunctionRecord(
                    name=rec.name,
                    package=package,
                    file=rec.file,
                    line=rec.line,
                    side_effects=rec.side_effects,
                )
            )
        else:
            filled.append(rec)

    return filled


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_source(
    source: str,
    filename: str,
    package: str,
) -> list[FunctionRecord]:
    """Analyze a single in-memory source string.

    Returns a list of ``FunctionRecord`` for each def/async def.  Results are
    ordered by ``(file, line, name)``.  No filesystem access.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except BROADENED_EXCEPTIONS as exc:
        print(
            f"snake-eyes: skipping {filename}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []

    try:
        records = _analyze_tree(tree, filename, package)
    except BROADENED_EXCEPTIONS as exc:
        print(
            f"snake-eyes: skipping {filename}: traversal error: {exc}",
            file=sys.stderr,
        )
        return []
    records.sort(key=lambda r: (r.file, r.line, r.name))
    return records


def analyze_path(
    root_path: str,
    patterns: list[str] | None,
) -> list[FunctionRecord]:
    """Analyze all discovered Python files under *root_path*.

    Returns a list of ``FunctionRecord`` ordered by ``(file, line, name)``.
    Parse-error / over-bound files are skipped-and-continued.
    Raises ``FileNotFoundError`` when *root_path* is missing (caller → -32602).
    """
    files = ordered_file_list(root_path, patterns)
    all_records: list[FunctionRecord] = []

    for rel_path, _source, tree in iter_source_files(root_path, files):
        package = derive_package(rel_path)
        try:
            records = _analyze_tree(tree, rel_path, package)
        except BROADENED_EXCEPTIONS as exc:
            print(
                f"snake-eyes: skipping {rel_path}: traversal error: {exc}",
                file=sys.stderr,
            )
            continue
        all_records.extend(records)

    all_records.sort(key=lambda r: (r.file, r.line, r.name))
    return all_records
