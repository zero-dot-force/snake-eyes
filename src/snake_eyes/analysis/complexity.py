# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: adapted for mypy --strict and ruff;
# extended for per-file resource bounds (stat/S_ISREG/byte-cap/depth budget);
# Go-only pattern lists removed; integrated with snake-eyes discovery/shared helpers.
"""Cyclomatic complexity computation for snake-eyes.

Lifted from the gaze-py McCabe AST walk and adapted for mypy --strict, ruff,
and the snake-eyes discovery/shared infrastructure.  No ``radon`` dependency.

Public entry point: ``compute_complexity(root_path, patterns)`` returns a
deterministic list of complexity entry dicts ordered by ``(file, line, name)``.
"""

from __future__ import annotations

import ast
import sys
from typing import Any

from ._shared import (
    BROADENED_EXCEPTIONS,
    MAX_AST_DEPTH,
    derive_package,
    iter_source_files,
    ordered_file_list,
)

# ---------------------------------------------------------------------------
# McCabe cyclomatic complexity — lifted from gaze-py
# ---------------------------------------------------------------------------

# Decision-point AST node types that each increment complexity by 1.
_DECISION_NODES: tuple[type[ast.AST], ...] = (
    ast.If,
    ast.While,
    ast.For,
    ast.ExceptHandler,
    ast.With,
    ast.Assert,  # note: assert is a branch in McCabe (control-flow split)
    ast.comprehension,
    ast.AsyncFor,
    ast.AsyncWith,
)


def _cyclomatic_complexity(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Compute the McCabe cyclomatic complexity for a single function node.

    Base complexity is 1 (the single linear path).  Each decision node adds 1;
    each additional boolean-operator operand beyond the first adds 1.
    """
    complexity = 1

    for node in ast.walk(func_node):
        if isinstance(node, _DECISION_NODES):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            # BoolOp.values has N operands → N-1 extra edges
            complexity += len(node.values) - 1
        elif isinstance(node, ast.IfExp):
            # Ternary a if cond else b adds one branch
            complexity += 1
        elif isinstance(node, ast.match_case):
            # Python 3.10+ structural pattern matching: each case is a branch
            complexity += 1

    return complexity


# ---------------------------------------------------------------------------
# Per-file function walker
# ---------------------------------------------------------------------------


class _ComplexityVisitor(ast.NodeVisitor):
    """Collect complexity entries for all def/async def in a module tree."""

    def __init__(self, rel_path: str) -> None:
        self._rel_path = rel_path
        self._package = derive_package(rel_path)
        self.entries: list[dict[str, Any]] = []
        self._depth = 0
        self._max_depth = MAX_AST_DEPTH

    def _check_depth(self) -> None:
        if self._depth > self._max_depth:
            raise RecursionError("AST depth budget exceeded in complexity visitor")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._depth += 1
        self._check_depth()
        self.entries.append(
            {
                "name": node.name,
                "package": self._package,
                "file": self._rel_path,
                "line": node.lineno,
                "complexity": _cyclomatic_complexity(node),
            }
        )
        self.generic_visit(node)
        self._depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._depth += 1
        self._check_depth()
        self.entries.append(
            {
                "name": node.name,
                "package": self._package,
                "file": self._rel_path,
                "line": node.lineno,
                "complexity": _cyclomatic_complexity(node),
            }
        )
        self.generic_visit(node)
        self._depth -= 1

    # Lambdas are NOT functions per spec — do not descend for complexity.
    def visit_Lambda(self, node: ast.Lambda) -> None:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_complexity(
    root_path: str,
    patterns: list[str] | None,
) -> list[dict[str, Any]]:
    """Return complexity entries for all functions in the discovered file set.

    The analyzed file set is the ordered concatenation of sorted source_files
    then test_files, de-duplicated preserving first occurrence (never a set
    union — determinism, Constitution I).

    Each entry carries ``name``, ``package``, ``file``, ``line``, and
    ``complexity`` (int).  The result is ordered by ``(file, line, name)``.

    Parse-error / over-bound files are skipped-and-continued; diagnostics go
    to stderr only.  Raises ``FileNotFoundError`` when *root_path* is missing
    (caller maps to -32602).
    """
    files = ordered_file_list(root_path, patterns)
    all_entries: list[dict[str, Any]] = []

    for rel_path, _source, tree in iter_source_files(root_path, files):
        visitor = _ComplexityVisitor(rel_path)
        try:
            visitor.visit(tree)
        except BROADENED_EXCEPTIONS:
            print(
                f"snake-eyes: skipping {rel_path}: traversal error",
                file=sys.stderr,
            )
            continue
        all_entries.extend(visitor.entries)

    all_entries.sort(key=lambda e: (e["file"], e["line"], e["name"]))
    return all_entries
