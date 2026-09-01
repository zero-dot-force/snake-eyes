# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: adapted for snake-eyes ast/models;
# exhaustive name-keyed classification table (not endswith heuristic);
# traversal scope and de-dup rules aligned with Gaze analyzer protocol v1.1.0;
# annotated for mypy --strict.
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

from ..analysis._shared import MAX_AST_DEPTH

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


# ---------------------------------------------------------------------------
# Public data type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssertionInfo:
    """A single assertion within a test function."""

    assertion_type: str  # one of the six types
    assertion_location: str  # "rel_path:line"
    line: int
    col: int  # col_offset for tiebreaking


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


def _collect_context_calls_stmt(stmt: ast.stmt, ids: set[int]) -> None:
    """Recursively collect with-item context Call ids from *stmt*."""
    if isinstance(stmt, ast.With):
        for item in stmt.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Call) and (
                _is_raises_warns_call(ctx) or _is_assert_raises_call(ctx)
            ):
                ids.add(id(ctx))
        for child in stmt.body:
            _collect_context_calls_stmt(child, ids)
    elif isinstance(stmt, (ast.For, ast.While)):
        for child in stmt.body:
            _collect_context_calls_stmt(child, ids)
        if hasattr(stmt, "orelse"):
            for child in stmt.orelse:
                _collect_context_calls_stmt(child, ids)
    elif isinstance(stmt, ast.If):
        for child in stmt.body:
            _collect_context_calls_stmt(child, ids)
        for child in stmt.orelse:
            _collect_context_calls_stmt(child, ids)
    elif isinstance(stmt, ast.Try):
        for child in stmt.body:
            _collect_context_calls_stmt(child, ids)
        for handler in stmt.handlers:
            for child in handler.body:
                _collect_context_calls_stmt(child, ids)
        for child in stmt.orelse:
            _collect_context_calls_stmt(child, ids)
        for child in stmt.finalbody:
            _collect_context_calls_stmt(child, ids)


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
        self.assertions: list[AssertionInfo] = []

    def _loc(self, node: ast.AST) -> str:
        line = getattr(node, "lineno", 0)
        return f"{self._rel_path}:{line}"

    def _col(self, node: ast.AST) -> int:
        return int(getattr(node, "col_offset", 0))

    def _line(self, node: ast.AST) -> int:
        return int(getattr(node, "lineno", 0))

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
            self.assertions.append(
                AssertionInfo(
                    assertion_type=atype,
                    assertion_location=self._loc(stmt),
                    line=self._line(stmt),
                    col=self._col(stmt),
                )
            )
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if id(call) not in self._skip_call_ids:
                call_atype = _classify_call(call)
                if call_atype is not None:
                    self.assertions.append(
                        AssertionInfo(
                            assertion_type=call_atype,
                            assertion_location=self._loc(call),
                            line=self._line(call),
                            col=self._col(call),
                        )
                    )
        elif isinstance(stmt, ast.With):
            for item in stmt.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and (
                    _is_raises_warns_call(ctx) or _is_assert_raises_call(ctx)
                ):
                    self.assertions.append(
                        AssertionInfo(
                            assertion_type="error_check",
                            assertion_location=self._loc(ctx),
                            line=self._line(ctx),
                            col=self._col(ctx),
                        )
                    )
            # Descend into with body
            self.visit_stmts(stmt.body)
        elif isinstance(stmt, (ast.For, ast.While)):
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
                self.visit_stmts(handler.body)
            if stmt.orelse:
                self.visit_stmts(stmt.orelse)
            if stmt.finalbody:
                self.visit_stmts(stmt.finalbody)
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
