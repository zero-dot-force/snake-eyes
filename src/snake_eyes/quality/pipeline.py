"""Test-mapping orchestration for snake-eyes.

FRESH — not lifted from gaze-py. No provenance header required.

Orchestrates discovery → analysis → test-function collection →
assertion detection → confidence computation → pairing → effect-type
inference → serialization.

Public API:
- ``run_test_mapping(root_path, patterns) -> TestMappingResult``
"""

from __future__ import annotations

import ast
import pathlib
import sys
from dataclasses import dataclass
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


def _collect_provenance(
    pair_tree: ast.Module,
    test_file: str,
    test_function: str,
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    resolver: ProvenanceResolver,
) -> tuple[Any, bool]:
    """Build container-state provenance context for one test function.

    Returns ``(provenance_context, provenance_ready)``. Falls back to an empty
    context (with ``provenance_ready=False``) when provenance construction
    raises, mirroring the container-mutation path.
    """
    try:
        return resolver.build_context(pair_tree, test_file, func_node), True
    except BROADENED_EXCEPTIONS as exc:
        print(
            f"snake-eyes: test_mapping disabling container-state provenance in"
            f" {test_file}/{test_function}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return resolver.empty_context(), False


@dataclass
class TestMappingResult:
    """Result of the test-mapping pipeline.

    ``mappings`` is the ordered list of protocol mapping rows (empty when
    there are no pairs). ``assertion_detection_confidence`` is the rounded
    percentage (0–100) of collected test functions in which at least one
    assertion was detected.
    """

    mappings: list[dict[str, Any]]
    assertion_detection_confidence: int


def run_test_mapping(
    root_path: str,
    patterns: list[str] | None,
) -> TestMappingResult:
    """Run the full test-mapping pipeline and return a result object.

    Each mapping row is a dict with exactly these keys:
    ``test_function, test_file, assertion_location, assertion_type,
    target_function, target_package, side_effect_type, confidence``.

    Returns a :class:`TestMappingResult` whose ``mappings`` is ``[]`` when
    there are no pairs, and whose ``assertion_detection_confidence`` is the
    rounded percentage of collected test functions with at least one
    detected assertion (``0`` when no test functions are collected).

    Raises ``FileNotFoundError`` when ``root_path`` is not a directory
    (caller maps to -32602).

    Static only: never runs pytest, reads coverage, or executes analyzed code.
    """
    # 1. Discover source and test files.
    discovered = discover(root_path, patterns)
    source_files = set(discovered.source_files)

    # 2. Analyze production (source) files for side effects.
    target_records = [
        record
        for record in analyze_path(root_path, patterns)
        if record.file in source_files
    ]

    root = pathlib.Path(root_path).resolve()
    resolver = ProvenanceResolver(root)

    # 3. Parse test files and collect test functions.
    test_files = list(discovered.test_files)
    test_trees, test_functions = _load_test_trees(root_path, test_files)

    # 4. Collect assertions + provenance context for every collected test
    #    function (paired or not) into maps keyed by (test_function, test_file).
    #    `collect_assertions` swallows RecursionError internally and returns
    #    partial results, so a degenerate walk yields a partial list rather
    #    than an error.
    assertions_by_test: dict[tuple[str, str], list[AssertionInfo]] = {}
    contexts_by_test: dict[
        tuple[str, str],
        tuple[ast.FunctionDef | ast.AsyncFunctionDef, Any, bool],
    ] = {}
    for test_name, rel_path in test_functions:
        test_tree = test_trees.get(rel_path)
        if test_tree is None:
            assertions_by_test[(test_name, rel_path)] = []
            continue
        func_node = _get_func_node(test_tree, test_name)
        if func_node is None:
            assertions_by_test[(test_name, rel_path)] = []
            continue
        try:
            assertions = collect_assertions(func_node, rel_path)
        except RecursionError:
            print(
                f"snake-eyes: test_mapping skipping assertions in"
                f" {rel_path}/{test_name}: depth budget exceeded",
                file=sys.stderr,
            )
            assertions = []
        except BROADENED_EXCEPTIONS as exc:
            print(
                f"snake-eyes: test_mapping skipping assertions in"
                f" {rel_path}/{test_name}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            assertions = []
        assertions_by_test[(test_name, rel_path)] = assertions

        provenance_context, provenance_ready = _collect_provenance(
            test_tree, rel_path, test_name, func_node, resolver
        )
        contexts_by_test[(test_name, rel_path)] = (
            func_node,
            provenance_context,
            provenance_ready,
        )

    # 5. Compute assertion-detection confidence (integer, round half up).
    total = len(assertions_by_test)
    detected = sum(1 for assertions in assertions_by_test.values() if assertions)
    if total > 0:
        confidence = (100 * detected + total // 2) // total
    else:
        confidence = 0

    # 6. Pair tests to production functions.
    # The graph node set includes BOTH source AND test files so that test-file
    # nodes have outgoing edges for transitive BFS (strategy 3).  Target
    # candidacy is still restricted to source-only `target_records` above.
    # With no production targets, every pairing strategy is a no-op, so skip
    # the (expensive) astroid call-graph build entirely.
    if target_records:
        graph_files = list(discovered.source_files) + list(discovered.test_files)
        pairs = pair_tests(
            test_functions=test_functions,
            target_records=target_records,
            test_trees=test_trees,
            root_abs=str(root),
            graph_files=graph_files,
        )
    else:
        pairs = []

    # 7. Build target-identity and import-package indexes for provenance.
    #    Built lazily: only when there are pairs to map (matching the
    #    container-mutation pipeline, which returned early on no pairs).
    target_records_by_identity: dict[tuple[str, str], FunctionRecord] = {}
    target_identity_counts: dict[tuple[str, str], int] = {}
    packages_by_file: dict[str, frozenset[str]] = {}
    target_import_packages: dict[tuple[str, str], frozenset[str]] = {}
    if pairs:
        for record in target_records:
            identity = (record.package, record.name)
            target_records_by_identity.setdefault(identity, record)
            target_identity_counts[identity] = (
                target_identity_counts.get(identity, 0) + 1
            )
        for record in target_records:
            if record.file not in packages_by_file:
                try:
                    packages_by_file[record.file] = resolver.target_packages(
                        record.file
                    )
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

    # 8. Build mapping rows from pre-collected assertions.
    rows: list[dict[str, Any]] = []

    for pair in pairs:
        assertions = assertions_by_test.get((pair.test_function, pair.test_file), [])
        context = contexts_by_test.get((pair.test_function, pair.test_file))
        if context is None:
            continue
        func_node, provenance_context, provenance_ready = context

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
                    # Internal tiebreaker fields (stripped before return)
                    "_line": assertion.line,
                    "_col": assertion.col,
                }
            )

    # 9. Sort by composite key (numeric line, col for tiebreaking).
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

    # 10. Strip internal tiebreaker fields.
    mappings = [
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

    return TestMappingResult(
        mappings=mappings,
        assertion_detection_confidence=confidence,
    )
