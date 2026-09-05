"""Test-mapping orchestration for snake-eyes.

FRESH — not lifted from gaze-py. No provenance header required.

Orchestrates discovery → analysis → test-function collection → pairing →
assertion detection → effect-type inference → serialization.

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
from ..analysis.models import FunctionRecord
from ..discovery import discover
from ._provenance import ProvenanceResolver
from .assertions import AssertionInfo, collect_assertions
from .mapping import infer_side_effect_type
from .pairing import pair_tests


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


def _collect_test_functions(tree: ast.Module) -> list[str]:
    """Collect top-level pytest and unittest test function names."""
    names: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                names.append(node.name)
        elif isinstance(node, ast.ClassDef) and _is_testcase_subclass(node):
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


def _load_test_trees(
    root_path: str,
    test_files: list[str],
) -> tuple[dict[str, ast.Module], list[tuple[str, str]]]:
    """Parse bounded test files and return trees plus named test functions."""
    test_trees: dict[str, ast.Module] = {}
    test_functions: list[tuple[str, str]] = []
    for rel_path, _source, tree in iter_source_files(root_path, test_files):
        try:
            enumerate_functions_with_spans(tree)
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
        test_functions.extend(
            (function_name, rel_path) for function_name in _collect_test_functions(tree)
        )
    return test_trees, test_functions


def _collect_assertion_context(
    pair_tree: ast.Module,
    test_file: str,
    test_function: str,
    resolver: ProvenanceResolver,
) -> (
    tuple[
        ast.FunctionDef | ast.AsyncFunctionDef,
        list[AssertionInfo],
        Any,
        bool,
    ]
    | None
):
    """Collect assertions and optional provenance for one test function."""
    func_node = _get_func_node(pair_tree, test_function)
    if func_node is None:
        return None
    try:
        assertions = collect_assertions(func_node, test_file)
    except RecursionError:
        print(
            f"snake-eyes: test_mapping skipping assertions in"
            f" {test_file}/{test_function}: depth budget exceeded",
            file=sys.stderr,
        )
        return None
    except BROADENED_EXCEPTIONS as exc:
        print(
            f"snake-eyes: test_mapping skipping assertions in"
            f" {test_file}/{test_function}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        provenance_context = resolver.build_context(pair_tree, test_file, func_node)
    except BROADENED_EXCEPTIONS as exc:
        print(
            f"snake-eyes: test_mapping disabling container-state provenance in"
            f" {test_file}/{test_function}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return func_node, assertions, resolver.empty_context(), False
    return func_node, assertions, provenance_context, True


def run_test_mapping(
    root_path: str,
    patterns: list[str] | None,
) -> list[dict[str, Any]]:
    """Run the test-mapping pipeline and return deterministic protocol rows.

    Each row contains exactly ``test_function``, ``test_file``,
    ``assertion_location``, ``assertion_type``, ``target_function``,
    ``target_package``, ``side_effect_type``, and ``confidence``. The function
    returns ``[]`` when there are no pairs and raises ``FileNotFoundError`` when
    ``root_path`` is not a directory. Analysis is static and never executes
    analyzed source or tests.
    """
    discovered = discover(root_path, patterns)
    source_files = set(discovered.source_files)
    target_records = [
        record
        for record in analyze_path(root_path, patterns)
        if record.file in source_files
    ]
    root = pathlib.Path(root_path).resolve()
    test_files = list(discovered.test_files)
    test_trees, test_functions = _load_test_trees(root_path, test_files)
    if not test_functions or not target_records:
        return []

    graph_files = list(discovered.source_files) + list(discovered.test_files)
    pairs = pair_tests(
        test_functions=test_functions,
        target_records=target_records,
        test_trees=test_trees,
        root_abs=str(root),
        graph_files=graph_files,
    )
    if not pairs:
        return []

    target_records_by_identity: dict[tuple[str, str], FunctionRecord] = {}
    target_identity_counts: dict[tuple[str, str], int] = {}
    for record in target_records:
        identity = (record.package, record.name)
        target_records_by_identity.setdefault(identity, record)
        target_identity_counts[identity] = target_identity_counts.get(identity, 0) + 1
    resolver = ProvenanceResolver(root)
    packages_by_file: dict[str, frozenset[str]] = {}
    for record in target_records:
        if record.file not in packages_by_file:
            try:
                packages_by_file[record.file] = resolver.target_packages(record.file)
            except BROADENED_EXCEPTIONS as exc:
                print(
                    f"snake-eyes: test_mapping disabling target provenance for"
                    f" {record.file}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                packages_by_file[record.file] = frozenset()
    target_import_packages = {
        (record.file, record.name): packages_by_file[record.file]
        for record in target_records
    }

    assertion_cache: dict[
        tuple[str, str],
        tuple[
            ast.FunctionDef | ast.AsyncFunctionDef,
            list[AssertionInfo],
            Any,
            bool,
        ],
    ] = {}
    rows: list[dict[str, Any]] = []

    for pair in pairs:
        pair_tree = test_trees.get(pair.test_file)
        if pair_tree is None:
            continue
        cache_key = (pair.test_file, pair.test_function)
        cached = assertion_cache.get(cache_key)
        if cached is None:
            collected = _collect_assertion_context(
                pair_tree,
                pair.test_file,
                pair.test_function,
                resolver,
            )
            if collected is None:
                continue
            cached = collected
            assertion_cache[cache_key] = cached
        func_node, assertions, provenance_context, provenance_ready = cached

        target_import_package = target_import_packages[
            (pair.target_file, pair.target_function)
        ]
        target_identity = (pair.target_package, pair.target_function)
        target_record = target_records_by_identity.get(target_identity)
        target_effects = target_record.side_effects if target_record is not None else ()
        for assertion in assertions:
            observes_container_state = (
                provenance_ready
                and target_identity_counts[target_identity] == 1
                and resolver.observes_container_state(
                    assertion,
                    func_node,
                    pair.target_function,
                    target_import_package,
                    provenance_context,
                )
            )
            rows.append(
                {
                    "test_function": pair.test_function,
                    "test_file": pair.test_file,
                    "assertion_location": assertion.assertion_location,
                    "assertion_type": assertion.assertion_type,
                    "target_function": pair.target_function,
                    "target_package": pair.target_package,
                    "side_effect_type": infer_side_effect_type(
                        assertion.assertion_type,
                        target_effects,
                        observes_container_state=observes_container_state,
                    ),
                    "confidence": pair.confidence,
                    "_line": assertion.line,
                    "_col": assertion.col,
                }
            )

    rows.sort(
        key=lambda row: (
            row["test_file"],
            row["test_function"],
            row["_line"],
            row["_col"],
            row["target_package"],
            row["target_function"],
        )
    )
    return [
        {
            "test_function": row["test_function"],
            "test_file": row["test_file"],
            "assertion_location": row["assertion_location"],
            "assertion_type": row["assertion_type"],
            "target_function": row["target_function"],
            "target_package": row["target_package"],
            "side_effect_type": row["side_effect_type"],
            "confidence": row["confidence"],
        }
        for row in rows
    ]
