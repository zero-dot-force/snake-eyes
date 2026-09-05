# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: adapted for snake-eyes ast/models;
# exhaustive name-keyed classification table (not endswith heuristic);
# traversal scope and de-dup rules aligned with Gaze analyzer protocol v1.1.0;
# internal container-state observation evidence; annotated for mypy --strict.
"""Assertion node identification and classification for snake-eyes.

Lifted from gaze-py ``quality/assertions.py`` and adapted for the snake-eyes
protocol (Gaze analyzer protocol v1.1.0).

Identifies assertion nodes in a test function's AST body and classifies each
into one of six ``assertion_type`` values:
``equality | comparison | identity | membership | error_check | generic``

Public API:
- ``collect_assertions(func_node, rel_path) -> list[AssertionInfo]``
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Literal

from ..analysis._shared import MAX_AST_DEPTH, _is_plain_len_call

# ---------------------------------------------------------------------------
# Classification tables (exhaustive name-keyed, not endswith heuristics)
# ---------------------------------------------------------------------------

_EQUALITY_METHODS: frozenset[str] = frozenset(
    {
        "assertEqual",
        "assertEquals",
        "assertAlmostEqual",
        "assertDictEqual",
        "assertListEqual",
        "assertMultiLineEqual",
        "assertCountEqual",
        "assertSequenceEqual",
    }
)

_COMPARISON_METHODS: frozenset[str] = frozenset(
    {
        "assertNotEqual",
        "assertNotAlmostEqual",
        "assertLess",
        "assertLessEqual",
        "assertGreater",
        "assertGreaterEqual",
    }
)

_IDENTITY_METHODS: frozenset[str] = frozenset(
    {
        "assertIs",
        "assertIsNot",
        "assertIsNone",
        "assertIsNotNone",
    }
)

_MEMBERSHIP_METHODS: frozenset[str] = frozenset(
    {
        "assertIn",
        "assertNotIn",
    }
)

_ERROR_CHECK_METHODS: frozenset[str] = frozenset(
    {
        "assertRaises",
        "assertRaisesRegex",
        "assertRaisesRegexp",
    }
)

_WARNS_METHODS: frozenset[str] = frozenset(
    {
        "assertWarns",
        "assertWarnsRegex",
    }
)

# Callee names that identify an error-check when used as a plain call or with-item
_ERROR_CHECK_CALLEES: frozenset[str] = frozenset({"raises", "warns"})
# Callees that indicate raises/warns as pytest.raises / pytest.warns attrs
_PYTEST_ATTRS: frozenset[str] = frozenset({"raises", "warns"})

_UNITTEST_OPERAND_NAMES: dict[str, tuple[str, ...]] = {
    "assertTrue": ("expr",),
    "assertFalse": ("expr",),
    "assertEqual": ("first", "second"),
    "assertEquals": ("first", "second"),
    "assertAlmostEqual": ("first", "second"),
    "assertDictEqual": ("d1", "d2"),
    "assertListEqual": ("list1", "list2"),
    "assertMultiLineEqual": ("first", "second"),
    "assertCountEqual": ("first", "second"),
    "assertSequenceEqual": ("seq1", "seq2"),
    "assertNotEqual": ("first", "second"),
    "assertNotAlmostEqual": ("first", "second"),
    "assertLess": ("a", "b"),
    "assertLessEqual": ("a", "b"),
    "assertGreater": ("a", "b"),
    "assertGreaterEqual": ("a", "b"),
    "assertIs": ("expr1", "expr2"),
    "assertIsNot": ("expr1", "expr2"),
    "assertIsNone": ("obj",),
    "assertIsNotNone": ("obj",),
    "assertIn": ("member", "container"),
    "assertNotIn": ("member", "container"),
    "assertRegex": ("text", "expected_regex"),
    "assertNotRegex": ("text", "expected_regex"),
    "assertIsInstance": ("obj", "cls"),
    "assertNotIsInstance": ("obj", "cls"),
}


# ---------------------------------------------------------------------------
# Public data type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContainerStateObservation:
    """An internal container-state syntax kind and its provenance candidate."""

    kind: Literal[
        "membership",
        "len",
        "subscript",
        "slice",
        "iteration",
        "comprehension",
    ]
    candidate: ast.expr


@dataclass(frozen=True)
class AssertionInfo:
    """A single assertion within a test function."""

    assertion_type: str  # one of the six types
    assertion_location: str  # "rel_path:line"
    line: int
    col: int  # col_offset for tiebreaking
    observations: tuple[ContainerStateObservation, ...] = ()
    expression: ast.expr | None = None


@dataclass
class _IterationContext:
    """Track whether a loop binding still denotes the iterated value."""

    observation: ContainerStateObservation
    bound_names: frozenset[str]
    active: bool = True


# ---------------------------------------------------------------------------
# Callee classification helpers
# ---------------------------------------------------------------------------


def _classify_by_method_name(method_name: str) -> str | None:
    """Return assertion_type for a known unittest assert* method, or None."""
    if method_name in _EQUALITY_METHODS:
        return "equality"
    if method_name in _COMPARISON_METHODS:
        return "comparison"
    if method_name in _IDENTITY_METHODS:
        return "identity"
    if method_name in _MEMBERSHIP_METHODS:
        return "membership"
    if method_name in _ERROR_CHECK_METHODS:
        return "error_check"
    if method_name in _WARNS_METHODS:
        return "error_check"
    # assertTrue, assertFalse, and any other assert* → generic
    if method_name.startswith("assert"):
        return "generic"
    return None


def _is_raises_warns_call(node: ast.Call) -> bool:
    """Return True if *node* is raises(...)/warns(...)/pytest.raises/pytest.warns."""
    fn = node.func
    if isinstance(fn, ast.Name) and fn.id in _ERROR_CHECK_CALLEES:
        return True
    if (
        isinstance(fn, ast.Attribute)
        and fn.attr in _PYTEST_ATTRS
        and isinstance(fn.value, ast.Name)
        and fn.value.id == "pytest"
    ):
        return True
    return False


def _is_assert_raises_call(node: ast.Call) -> bool:
    """Return True if *node* is self.assertRaises(...) / similar."""
    fn = node.func
    if isinstance(fn, ast.Attribute) and fn.attr in _ERROR_CHECK_METHODS:
        return True
    return False


def _classify_assert_stmt(node: ast.Assert) -> str:
    """Classify a bare ``assert`` statement by its test expression."""
    test = node.test
    if isinstance(test, ast.Compare):
        ops = test.ops
        if ops:
            op = ops[0]
            if isinstance(op, ast.Eq):
                return "equality"
            if isinstance(op, (ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                return "comparison"
            if isinstance(op, (ast.Is, ast.IsNot)):
                return "identity"
            if isinstance(op, (ast.In, ast.NotIn)):
                return "membership"
    return "generic"


def _classify_call(node: ast.Call) -> str | None:
    """Return assertion_type if this Call is an assertion; else None."""
    fn = node.func

    # self.assertXxx(...) or bare assertXxx(...)
    if isinstance(fn, ast.Attribute):
        atype = _classify_by_method_name(fn.attr)
        if atype is not None:
            return atype
        # pytest.raises / pytest.warns
        if fn.attr in _PYTEST_ATTRS and isinstance(fn.value, ast.Name):
            if fn.value.id == "pytest":
                return "error_check"

    # bare function call: raises(...), warns(...)
    if isinstance(fn, ast.Name):
        if fn.id in _ERROR_CHECK_CALLEES:
            return "error_check"

    return None


# ---------------------------------------------------------------------------
# Internal container-state observation evidence
# ---------------------------------------------------------------------------


def _append_expression_observations(
    node: ast.AST,
    observations: list[ContainerStateObservation],
    *,
    depth: int,
    max_depth: int,
) -> None:
    """Append supported observations in deterministic AST field order."""
    if depth > max_depth:
        raise RecursionError("AST depth budget exceeded in observation collector")

    if isinstance(node, ast.Lambda):
        return

    if isinstance(node, ast.Compare):
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            if isinstance(operator, (ast.In, ast.NotIn)):
                observations.append(
                    ContainerStateObservation(kind="membership", candidate=comparator)
                )

    if isinstance(node, ast.Call) and _is_plain_len_call(node):
        observations.append(
            ContainerStateObservation(kind="len", candidate=node.args[0])
        )

    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _MEMBERSHIP_METHODS
        and len(node.args) >= 2
    ):
        observations.append(
            ContainerStateObservation(kind="membership", candidate=node.args[1])
        )

    if isinstance(node, ast.Subscript):
        kind: Literal["subscript", "slice"] = (
            "slice" if isinstance(node.slice, ast.Slice) else "subscript"
        )
        observations.append(ContainerStateObservation(kind=kind, candidate=node.value))

    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        observations.extend(
            ContainerStateObservation(kind="comprehension", candidate=generator.iter)
            for generator in node.generators
        )

    for child in ast.iter_child_nodes(node):
        _append_expression_observations(
            child,
            observations,
            depth=depth + 1,
            max_depth=max_depth,
        )


def _append_loaded_names(
    node: ast.AST,
    names: set[str],
    *,
    depth: int,
    max_depth: int,
    excluded: frozenset[str] = frozenset(),
) -> None:
    """Append loaded names without crossing a nested lambda scope."""
    if depth > max_depth:
        raise RecursionError("AST depth budget exceeded in observation collector")
    if isinstance(node, ast.Lambda):
        return
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        if node.id not in excluded:
            names.add(node.id)
        return
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        local_excluded = set(excluded)
        for generator in node.generators:
            _append_loaded_names(
                generator.iter,
                names,
                depth=depth + 1,
                max_depth=max_depth,
                excluded=frozenset(local_excluded),
            )
            local_excluded.update(_bound_names(generator.target))
            for condition in generator.ifs:
                _append_loaded_names(
                    condition,
                    names,
                    depth=depth + 1,
                    max_depth=max_depth,
                    excluded=frozenset(local_excluded),
                )
        projected_nodes: tuple[ast.AST, ...]
        if isinstance(node, ast.DictComp):
            projected_nodes = (node.key, node.value)
        else:
            projected_nodes = (node.elt,)
        for projected in projected_nodes:
            _append_loaded_names(
                projected,
                names,
                depth=depth + 1,
                max_depth=max_depth,
                excluded=frozenset(local_excluded),
            )
        return
    for child in ast.iter_child_nodes(node):
        _append_loaded_names(
            child,
            names,
            depth=depth + 1,
            max_depth=max_depth,
            excluded=excluded,
        )


def _bound_names(target: ast.expr) -> frozenset[str]:
    """Return simple names bound by a for-loop target."""
    if isinstance(target, ast.Name):
        return frozenset({target.id})
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        return frozenset(
            name for element in target.elts for name in _bound_names(element)
        )
    return frozenset()


def _append_stored_names(
    node: ast.AST,
    names: set[str],
    *,
    depth: int = 1,
) -> None:
    """Append names rebound or deleted by one non-scope statement."""
    if depth > MAX_AST_DEPTH:
        raise RecursionError("AST depth budget exceeded in iteration provenance")
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.add(node.name)
        return
    if isinstance(node, ast.Lambda):
        return
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        names.add(node.id)
    if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(
        node.ctx, (ast.Store, ast.Del)
    ):
        _append_loaded_names(node.value, names, depth=1, max_depth=MAX_AST_DEPTH)
    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name is not None:
        names.add(node.name)
    if isinstance(node, ast.MatchMapping) and node.rest is not None:
        names.add(node.rest)
    for child in ast.iter_child_nodes(node):
        _append_stored_names(child, names, depth=depth + 1)


def _append_escaped_names(
    node: ast.AST,
    names: set[str],
    *,
    depth: int = 1,
) -> None:
    """Append names passed to potentially mutating calls or assigned as aliases."""
    if depth > MAX_AST_DEPTH:
        raise RecursionError("AST depth budget exceeded in iteration provenance")
    if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    ):
        return
    if isinstance(node, ast.Call):
        if not _is_plain_len_call(node):
            _append_loaded_names(node, names, depth=1, max_depth=MAX_AST_DEPTH)
            return
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        value = getattr(node, "value", None)
        if isinstance(value, ast.expr):
            _append_loaded_names(value, names, depth=1, max_depth=MAX_AST_DEPTH)
    for child in ast.iter_child_nodes(node):
        _append_escaped_names(child, names, depth=depth + 1)


# ---------------------------------------------------------------------------
# Context-expression skip set: calls that are WITH-item context expressions
# (these are collected as with-items, NOT as bare calls)
# ---------------------------------------------------------------------------


def _collect_with_context_calls(stmts: list[ast.stmt]) -> set[int]:
    """Return id() of Call nodes used as with-item context expressions.

    These calls should be counted once as the with-item, never additionally
    as a bare call in visit_Call.
    """
    ids: set[int] = set()
    for stmt in stmts:
        _collect_context_calls_stmt(stmt, ids)
    return ids


def _collect_context_calls_stmt(
    stmt: ast.stmt,
    ids: set[int],
    *,
    depth: int = 1,
) -> None:
    """Recursively collect with-item context Call ids from *stmt*."""
    if depth > MAX_AST_DEPTH:
        raise RecursionError("AST depth budget exceeded in context-call collector")
    if isinstance(stmt, ast.With):
        for item in stmt.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Call) and (
                _is_raises_warns_call(ctx) or _is_assert_raises_call(ctx)
            ):
                ids.add(id(ctx))
        for child in stmt.body:
            _collect_context_calls_stmt(child, ids, depth=depth + 1)
    elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
        for child in stmt.body:
            _collect_context_calls_stmt(child, ids, depth=depth + 1)
        if hasattr(stmt, "orelse"):
            for child in stmt.orelse:
                _collect_context_calls_stmt(child, ids, depth=depth + 1)
    elif isinstance(stmt, ast.If):
        for child in stmt.body:
            _collect_context_calls_stmt(child, ids, depth=depth + 1)
        for child in stmt.orelse:
            _collect_context_calls_stmt(child, ids, depth=depth + 1)
    elif isinstance(stmt, ast.Try):
        for child in stmt.body:
            _collect_context_calls_stmt(child, ids, depth=depth + 1)
        for handler in stmt.handlers:
            for child in handler.body:
                _collect_context_calls_stmt(child, ids, depth=depth + 1)
        for child in stmt.orelse:
            _collect_context_calls_stmt(child, ids, depth=depth + 1)
        for child in stmt.finalbody:
            _collect_context_calls_stmt(child, ids, depth=depth + 1)


# ---------------------------------------------------------------------------
# AST visitor
# ---------------------------------------------------------------------------


class _AssertionVisitor:
    """Collect assertions from a function body (no nested defs/classes)."""

    def __init__(
        self,
        rel_path: str,
        skip_call_ids: set[int],
        max_depth: int,
    ) -> None:
        self._rel_path = rel_path
        self._skip_call_ids = skip_call_ids
        self._max_depth = max_depth
        self._depth = 0
        self._iteration_contexts: list[_IterationContext] = []
        self.assertions: list[AssertionInfo] = []

    def _loc(self, node: ast.AST) -> str:
        line = getattr(node, "lineno", 0)
        return f"{self._rel_path}:{line}"

    def _col(self, node: ast.AST) -> int:
        return int(getattr(node, "col_offset", 0))

    def _line(self, node: ast.AST) -> int:
        return int(getattr(node, "lineno", 0))

    def _observations(
        self, expression: ast.expr | None
    ) -> tuple[ContainerStateObservation, ...]:
        if expression is None:
            return ()
        observations: list[ContainerStateObservation] = []
        loaded_names: set[str] = set()
        escaped_names: set[str] = set()
        try:
            _append_expression_observations(
                expression,
                observations,
                depth=1,
                max_depth=self._max_depth,
            )
            if self._iteration_contexts:
                _append_loaded_names(
                    expression,
                    loaded_names,
                    depth=1,
                    max_depth=self._max_depth,
                )
                _append_escaped_names(expression, escaped_names)
        except RecursionError:
            # Over-budget evidence is ambiguous, so preserve the prior mapping.
            return ()

        observations.extend(
            context.observation
            for context in self._iteration_contexts
            if context.active
            and loaded_names & context.bound_names
            and not escaped_names & context.bound_names
        )
        return tuple(observations)

    def _invalidate_iteration_bindings(self, node: ast.AST) -> None:
        """Invalidate loop evidence after a bound name is rebound or deleted."""
        stored_names: set[str] = set()
        escaped_names: set[str] = set()
        _append_stored_names(node, stored_names)
        _append_escaped_names(node, escaped_names)
        for context in self._iteration_contexts:
            if context.bound_names & (stored_names | escaped_names):
                context.active = False

    def _append_assertion(
        self,
        assertion_type: str,
        location_node: ast.AST,
        expression: ast.expr | None = None,
    ) -> None:
        self.assertions.append(
            AssertionInfo(
                assertion_type=assertion_type,
                assertion_location=self._loc(location_node),
                line=self._line(location_node),
                col=self._col(location_node),
                observations=self._observations(expression),
                expression=expression,
            )
        )

    @staticmethod
    def _call_asserted_expression(call: ast.Call) -> ast.expr:
        """Return only the operands that determine a unittest assertion result."""
        method_name = ""
        if isinstance(call.func, ast.Attribute):
            method_name = call.func.attr
        elif isinstance(call.func, ast.Name):
            method_name = call.func.id

        operand_names = _UNITTEST_OPERAND_NAMES.get(method_name)
        if operand_names is None:
            # Unknown assertion methods are opt-out: no evidence is collected,
            # so downstream provenance cannot fabricate container-state credit.
            return ast.Tuple(elts=[], ctx=ast.Load())

        keyword_values = {keyword.arg: keyword.value for keyword in call.keywords}
        operands = [
            call.args[index] if index < len(call.args) else keyword_values[name]
            for index, name in enumerate(operand_names)
            if index < len(call.args) or name in keyword_values
        ]
        if method_name in _MEMBERSHIP_METHODS and len(operands) >= 2:
            return ast.Compare(
                left=operands[0],
                ops=[ast.In()],
                comparators=[operands[1]],
            )
        if len(operands) == 1:
            return operands[0]
        return ast.Tuple(elts=list(operands), ctx=ast.Load())

    def visit_stmts(self, stmts: list[ast.stmt]) -> None:
        self._depth += 1
        if self._depth > self._max_depth:
            raise RecursionError("AST depth budget exceeded in assertion visitor")
        for stmt in stmts:
            self.visit_stmt(stmt)
        self._depth -= 1

    def visit_stmt(self, stmt: ast.stmt) -> None:
        if isinstance(stmt, ast.Assert):
            atype = _classify_assert_stmt(stmt)
            self._append_assertion(atype, stmt, stmt.test)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if id(call) not in self._skip_call_ids:
                call_atype = _classify_call(call)
                if call_atype is not None:
                    expression = (
                        None
                        if call_atype == "error_check"
                        else self._call_asserted_expression(call)
                    )
                    self._append_assertion(call_atype, call, expression)
                else:
                    self._invalidate_iteration_bindings(stmt)
        elif isinstance(stmt, ast.With):
            for item in stmt.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and (
                    _is_raises_warns_call(ctx) or _is_assert_raises_call(ctx)
                ):
                    self._append_assertion("error_check", ctx)
                if item.optional_vars is not None:
                    self._invalidate_iteration_bindings(item.optional_vars)
            # Descend into with body
            self.visit_stmts(stmt.body)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            self._invalidate_iteration_bindings(stmt.target)
            context = _IterationContext(
                observation=ContainerStateObservation(
                    kind="iteration", candidate=stmt.iter
                ),
                bound_names=_bound_names(stmt.target),
            )
            self._iteration_contexts.append(context)
            try:
                self.visit_stmts(stmt.body)
            finally:
                self._iteration_contexts.pop()
            if stmt.orelse:
                self.visit_stmts(stmt.orelse)
        elif isinstance(stmt, ast.While):
            self.visit_stmts(stmt.body)
            if stmt.orelse:
                self.visit_stmts(stmt.orelse)
        elif isinstance(stmt, ast.If):
            self.visit_stmts(stmt.body)
            if stmt.orelse:
                self.visit_stmts(stmt.orelse)
        elif isinstance(stmt, ast.Try):
            self.visit_stmts(stmt.body)
            for handler in stmt.handlers:
                if handler.name is not None:
                    for context in self._iteration_contexts:
                        if handler.name in context.bound_names:
                            context.active = False
                self.visit_stmts(handler.body)
            if stmt.orelse:
                self.visit_stmts(stmt.orelse)
            if stmt.finalbody:
                self.visit_stmts(stmt.finalbody)
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                self._invalidate_iteration_bindings(case.pattern)
                self.visit_stmts(case.body)
        else:
            self._invalidate_iteration_bindings(stmt)
        # Do NOT descend into FunctionDef / AsyncFunctionDef / ClassDef


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_assertions(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    rel_path: str,
) -> list[AssertionInfo]:
    """Collect assertions from a test function node.

    *rel_path* is the test file path relative to the project root (POSIX),
    used to format ``assertion_location`` as ``rel_path:line``.

    Traverses the direct body (nested ``with``/``for``/``if``/``while``/``try``
    included); does NOT descend into nested ``def``/``class`` bodies.
    """
    body: list[ast.stmt] = list(func_node.body)
    skip_ids = _collect_with_context_calls(body)
    visitor = _AssertionVisitor(rel_path, skip_ids, max_depth=MAX_AST_DEPTH)
    try:
        visitor.visit_stmts(body)
    except RecursionError:
        pass
    return visitor.assertions
