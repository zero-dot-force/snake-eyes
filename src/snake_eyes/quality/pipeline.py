"""Test-mapping pipeline for snake-eyes.

FRESH — not lifted from gaze-py. No provenance header required.

Orchestrates discovery → analysis → test-function collection → pairing →
assertion detection → effect-type inference → serialisation.

Public API:
- ``run_test_mapping(root_path, patterns) -> list[dict]``
"""

from __future__ import annotations

import ast
import pathlib
import sys
from typing import Any

from ..analysis._shared import (
    BROADENED_EXCEPTIONS,
    enumerate_functions_with_spans,
    iter_source_files,
)
from ..analysis.detector import analyze_path
from ..discovery import discover
from .assertions import collect_assertions
from .mapping import infer_side_effect_type
from .pairing import pair_tests

# ---------------------------------------------------------------------------
# Test-function collection helpers
# ---------------------------------------------------------------------------


def _is_testcase_subclass(class_node: ast.ClassDef) -> bool:
    """Return True if *class_node* appears to subclass unittest.TestCase."""
    for base in class_node.bases:
        if isinstance(base, ast.Name) and base.id == "TestCase":
            return True
        if (
            isinstance(base, ast.Attribute)
            and base.attr == "TestCase"
            and isinstance(base.value, ast.Name)
            and base.value.id == "unittest"
        ):
            return True
    return False


def _collect_test_functions(
    tree: ast.Module,
) -> list[str]:
    """Collect test function names from an AST module.

    Returns bare names for top-level ``test_*`` functions and
    ``ClassName.method`` for ``test*`` methods of ``unittest.TestCase``
    subclasses.
    """
    names: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            if _is_testcase_subclass(node):
                for item in node.body:
                    if isinstance(
                        item, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and item.name.startswith("test"):
                        names.append(f"{node.name}.{item.name}")
    return names


def _get_func_node(
    tree: ast.Module,
    test_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Look up the AST node for *test_name* (bare or Class.method)."""
    if "." in test_name:
        class_name, method_name = test_name.split(".", 1)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if (
                        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name == method_name
                    ):
                        return item
        return None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == test_name:
                return node
    return None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_test_mapping(
    root_path: str,
    patterns: list[str] | None,
) -> list[dict[str, Any]]:
    """Run the full test-mapping pipeline and return a list of mapping rows.

    Each row is a dict with exactly these keys:
    ``test_function, test_file, assertion_location, assertion_type,
    target_function, target_package, side_effect_type, confidence``.

    Returns ``[]`` when there are no pairs.

    Raises ``FileNotFoundError`` when ``root_path`` is not a directory
    (caller maps to -32602).

    Static only: never runs pytest, reads coverage, or executes analyzed code.
    """
    # 1. Discover source and test files
    disc = discover(root_path, patterns)
    source_files_set: set[str] = set(disc.source_files)

    # 2. Analyze all production (source) files for side effects
    all_records = analyze_path(root_path, patterns)
    # Filter to production files only (never test files)
    target_records = [r for r in all_records if r.file in source_files_set]

    root = pathlib.Path(root_path).resolve()

    # 3. Parse test files and collect test functions
    test_files: list[str] = list(disc.test_files)
    test_trees: dict[str, ast.Module] = {}
    test_functions: list[tuple[str, str]] = []  # (name, test_file)

    for rel_path, _source, tree in iter_source_files(root_path, test_files):
        # Guard depth: use enumerate_functions_with_spans which is depth-guarded
        try:
            _ = enumerate_functions_with_spans(tree)
        except RecursionError:
            print(
                f"snake-eyes: test_mapping skipping {rel_path}:"
                " AST depth budget exceeded",
                file=sys.stderr,
            )
            continue
        except BROADENED_EXCEPTIONS as exc:
            print(
                f"snake-eyes: test_mapping skipping {rel_path}:"
                f" {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue

        test_trees[rel_path] = tree
        funcs = _collect_test_functions(tree)
        for fn in funcs:
            test_functions.append((fn, rel_path))

    if not test_functions or not target_records:
        return []

    # 4. Pair tests to production functions
    pairs = pair_tests(
        test_functions=test_functions,
        target_records=target_records,
        test_trees=test_trees,
        root_abs=str(root),
        all_source_files=list(disc.source_files),
    )

    if not pairs:
        return []

    # 5. Collect assertions and build mapping rows
    rows: list[dict[str, Any]] = []

    for pair in pairs:
        pair_tree = test_trees.get(pair.test_file)
        if pair_tree is None:
            continue

        func_node = _get_func_node(pair_tree, pair.test_function)
        if func_node is None:
            continue

        # Collect assertions — guard depth
        try:
            assertions = collect_assertions(func_node, pair.test_file)
        except RecursionError:
            print(
                f"snake-eyes: test_mapping skipping assertions in"
                f" {pair.test_file}/{pair.test_function}: depth budget exceeded",
                file=sys.stderr,
            )
            continue
        except BROADENED_EXCEPTIONS as exc:
            print(
                f"snake-eyes: test_mapping skipping assertions in"
                f" {pair.test_file}/{pair.test_function}:"
                f" {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue

        # Find target record for side-effect inference
        target_rec = next(
            (
                r
                for r in target_records
                if r.name == pair.target_function and r.package == pair.target_package
            ),
            None,
        )
        target_effects = target_rec.side_effects if target_rec is not None else ()

        for assertion in assertions:
            side_effect_type = infer_side_effect_type(
                assertion.assertion_type, target_effects
            )
            rows.append(
                {
                    "test_function": pair.test_function,
                    "test_file": pair.test_file,
                    "assertion_location": assertion.assertion_location,
                    "assertion_type": assertion.assertion_type,
                    "target_function": pair.target_function,
                    "target_package": pair.target_package,
                    "side_effect_type": side_effect_type,
                    "confidence": pair.confidence,
                    # Internal tiebreaker fields (stripped before return)
                    "_line": assertion.line,
                    "_col": assertion.col,
                }
            )

    # 6. Sort by composite key (numeric line, col for tiebreaking)
    rows.sort(
        key=lambda r: (
            r["test_file"],
            r["test_function"],
            r["_line"],
            r["_col"],
            r["target_package"],
            r["target_function"],
        )
    )

    # Strip internal tiebreaker fields
    return [
        {
            "test_function": r["test_function"],
            "test_file": r["test_file"],
            "assertion_location": r["assertion_location"],
            "assertion_type": r["assertion_type"],
            "target_function": r["target_function"],
            "target_package": r["target_package"],
            "side_effect_type": r["side_effect_type"],
            "confidence": r["confidence"],
        }
        for r in rows
    ]
