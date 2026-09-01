# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: adapted for snake-eyes ast/models; lifted
# 0.0-1.0 confidence scores converted to int 0-100; astroid transitive call
# graph (strategy 3) ported with snake-eyes MANAGER lifecycle inline;
# Go-only patterns removed; integrated with snake-eyes protocol models.
"""Test-function pairing engine for snake-eyes.

Lifted from gaze-py ``quality/pairing.py`` and adapted for the snake-eyes
protocol (Gaze analyzer protocol v1.1.0).

Three-strategy, first-match-wins pairing:

1. **Name convention** -- strip leading ``test_``/``Test``/``test``/``Test``
   prefix; exact match → confidence 90, case-only match → confidence 70.
2. **Direct call** -- target name appears as a ``Call`` in the test AST
   → confidence 80.
3. **Transitive call graph** -- astroid BFS with ``depth_limit=5``
   → confidence 75; built once per ``run_test_mapping`` request (lazy).

Public API:
- ``pair_tests(test_functions, target_records, test_trees) -> list[PairedResult]``
"""

from __future__ import annotations

import ast
import pathlib
import sys
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import astroid  # type: ignore[import-untyped]
from astroid import nodes as astroid_nodes
from astroid.exceptions import AstroidError  # type: ignore[import-untyped]
from astroid.util import Uninferable  # type: ignore[import-untyped]

from ..analysis._shared import derive_package

if TYPE_CHECKING:
    from ..analysis.models import FunctionRecord

# Broadened exception tuple for strategy 3 (mirrors analysis/inference.py).
# FileNotFoundError is intentionally excluded so discover() errors propagate.
_STRATEGY3_DEGRADE: tuple[type[BaseException], ...] = (
    AstroidError,
    RecursionError,
    MemoryError,
)

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairedResult:
    """A single (test, target) pairing."""

    test_function: str
    test_file: str
    target_function: str
    target_package: str
    target_file: str
    confidence: int  # 0–100 integer per protocol


# ---------------------------------------------------------------------------
# Name-stripping helpers (Strategy 1)
# ---------------------------------------------------------------------------


def _strip_test_prefix(name: str) -> str | None:
    """Return the name with a leading test prefix stripped, or None."""
    # snake_case: test_foo -> foo
    if name.startswith("test_") and len(name) > len("test_"):
        return name[len("test_") :]
    # snake_case short: testfoo -> foo (bare 'test' prefix without underscore)
    if name.startswith("test") and len(name) > len("test") and not name[4:5] == "_":
        return name[len("test") :]
    # CamelCase: TestFoo -> Foo  (class method style with leading capital)
    if name.startswith("Test") and len(name) > len("Test"):
        return name[len("Test") :]
    return None


def _name_match(
    test_name: str,
    target_records: list[FunctionRecord],
) -> list[tuple[FunctionRecord, int]]:
    """Return list of (record, confidence) for name-convention strategy."""
    # Extract the bare name (without class qualifier) for matching
    bare = test_name.split(".")[-1]
    stripped = _strip_test_prefix(bare)
    if stripped is None:
        return []
    results: list[tuple[FunctionRecord, int]] = []
    for rec in target_records:
        if rec.name == stripped:
            results.append((rec, 90))
        elif rec.name.lower() == stripped.lower():
            results.append((rec, 70))
    return results


# ---------------------------------------------------------------------------
# Direct-call helpers (Strategy 2)
# ---------------------------------------------------------------------------


def _direct_call_names(tree: ast.Module, func_name: str) -> set[str]:
    """Return the set of callee names directly called in *func_name*."""
    # Find the function node — bare name or Class.method
    target_node: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    bare = func_name.split(".")[-1]
    class_part = func_name.split(".")[0] if "." in func_name else None

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and class_part and node.name == class_part:
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == bare
                ):
                    target_node = item
                    break
        elif (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == func_name
            and class_part is None
        ):
            target_node = node

    if target_node is None:
        return set()

    names: set[str] = set()
    for child in ast.walk(target_node):
        if isinstance(child, ast.Call):
            fn = child.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def _direct_call_match(
    test_name: str,
    test_tree: ast.Module,
    target_records: list[FunctionRecord],
) -> list[tuple[FunctionRecord, int]]:
    """Return list of (record, confidence=80) for direct-call strategy."""
    called = _direct_call_names(test_tree, test_name)
    results: list[tuple[FunctionRecord, int]] = []
    for rec in target_records:
        if rec.name in called:
            results.append((rec, 80))
    return results


# ---------------------------------------------------------------------------
# Transitive call graph (Strategy 3) — built lazily, once per request
# ---------------------------------------------------------------------------


@dataclass
class _CallGraph:
    """Maps normalized file path → set of normalized callee file paths."""

    edges: dict[str, set[str]]

    def reachable_files(self, start_file: str, depth_limit: int = 5) -> set[str]:
        """BFS from *start_file*; return all files reachable within depth_limit."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        queue.append((start_file, 0))
        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > depth_limit:
                continue
            visited.add(current)
            for neighbour in self.edges.get(current, set()):
                if neighbour not in visited and depth + 1 <= depth_limit:
                    queue.append((neighbour, depth + 1))
        return visited


def _normalize_path(p: str) -> str:
    return str(pathlib.Path(p).resolve())


def _build_call_graph(
    root_abs: str,
    all_source_files: list[str],
) -> _CallGraph | None:
    """Build an astroid call graph; return None on any degrade."""
    try:
        manager = astroid.MANAGER
        manager.clear_cache()

        edges: dict[str, set[str]] = {}
        # list of (norm_path, module) pairs
        parsed: list[tuple[str, Any]] = []

        root = pathlib.Path(root_abs)

        for rel in all_source_files:
            abs_path = root / rel
            try:
                modname = derive_package(rel)
                module = manager.ast_from_file(str(abs_path), modname, source=True)
                norm = _normalize_path(str(abs_path))
                parsed.append((norm, module))
            except FileNotFoundError:
                raise
            except Exception as exc:
                print(
                    f"snake-eyes: test_mapping strategy-3 skipping {rel}:"
                    f" {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                continue

        analyzed_norms: set[str] = {norm for norm, _ in parsed}

        for source_norm, module in parsed:
            try:
                call_iter = module.nodes_of_class(astroid_nodes.Call)
            except Exception:
                continue
            for call in call_iter:
                fn = call.func
                callee_name: str | None = None
                if isinstance(fn, astroid_nodes.Name):
                    callee_name = fn.name
                elif isinstance(fn, astroid_nodes.Attribute):
                    callee_name = fn.attrname
                if callee_name is None:
                    continue
                try:
                    inferred = list(call.func.infer())
                except Exception:
                    continue
                for candidate in inferred:
                    try:
                        if candidate is Uninferable:
                            continue
                        if not isinstance(
                            candidate,
                            (
                                astroid_nodes.FunctionDef,
                                astroid_nodes.AsyncFunctionDef,
                            ),
                        ):
                            continue
                        callee_file = getattr(candidate.root(), "file", None)
                        if callee_file is None:
                            continue
                        callee_norm = _normalize_path(callee_file)
                        if callee_norm in analyzed_norms:
                            edges.setdefault(source_norm, set()).add(callee_norm)
                    except Exception:
                        continue

        return _CallGraph(edges=edges)

    except FileNotFoundError:
        raise
    except (AstroidError, RecursionError, MemoryError) as exc:
        print(
            f"snake-eyes: test_mapping strategy-3 call graph build failed:"
            f" {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None
    except Exception as exc:
        print(
            f"snake-eyes: test_mapping strategy-3 call graph build failed"
            f" (unexpected): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


def _transitive_match(
    test_file_norm: str,
    call_graph: _CallGraph,
    target_records: list[FunctionRecord],
    depth_limit: int = 5,
) -> list[tuple[FunctionRecord, int]]:
    """Match via BFS call graph reachability, confidence 75."""
    reachable = call_graph.reachable_files(test_file_norm, depth_limit)
    results: list[tuple[FunctionRecord, int]] = []
    for rec in target_records:
        rec_norm = _normalize_path(rec.file)
        if rec_norm in reachable:
            results.append((rec, 75))
    return results


# ---------------------------------------------------------------------------
# Main pairing function
# ---------------------------------------------------------------------------


def pair_tests(
    test_functions: list[tuple[str, str]],  # (name, test_file)
    target_records: list[FunctionRecord],
    test_trees: dict[str, ast.Module],  # test_file -> AST
    root_abs: str,
    all_source_files: list[str],
) -> list[PairedResult]:
    """Pair test functions to production functions using three strategies.

    Returns one ``PairedResult`` per unique ``(test_function, test_file,
    target_package, target_function)`` key, in first-match-wins priority order.
    """
    results: list[PairedResult] = []
    seen: set[tuple[str, str, str, str]] = set()

    # Lazy call graph for strategy 3: None = disabled/failed, False = not yet tried
    _graph: _CallGraph | None | bool = False

    def _get_graph() -> _CallGraph | None:
        nonlocal _graph
        if _graph is False:
            try:
                _graph = _build_call_graph(root_abs, all_source_files)
            except FileNotFoundError:
                raise
            except Exception as exc:
                print(
                    f"snake-eyes: test_mapping strategy-3 disabled:"
                    f" {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                _graph = None
        # _graph is now None or a _CallGraph (bool False was the sentinel)
        if isinstance(_graph, _CallGraph):
            return _graph
        return None

    try:
        for test_name, test_file in test_functions:
            tree = test_trees.get(test_file)
            if tree is None:
                continue

            paired: list[tuple[FunctionRecord, int]] = []

            # Strategy 1: name convention
            paired = _name_match(test_name, target_records)

            # Strategy 2: direct call (only if strategy 1 found nothing)
            if not paired:
                paired = _direct_call_match(test_name, tree, target_records)

            # Strategy 3: transitive call graph (only if strategies 1+2 empty)
            if not paired:
                try:
                    graph = _get_graph()
                    if graph is not None:
                        test_abs = str((pathlib.Path(root_abs) / test_file).resolve())
                        paired = _transitive_match(test_abs, graph, target_records)
                except FileNotFoundError:
                    raise
                except Exception as exc:
                    print(
                        f"snake-eyes: test_mapping strategy-3 lookup failed:"
                        f" {type(exc).__name__}: {exc}",
                        file=sys.stderr,
                    )

            # Emit one result per distinct (target_package, target_function), de-dup
            for rec, confidence in paired:
                key = (test_name, test_file, rec.package, rec.name)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    PairedResult(
                        test_function=test_name,
                        test_file=test_file,
                        target_function=rec.name,
                        target_package=rec.package,
                        target_file=rec.file,
                        confidence=confidence,
                    )
                )
    finally:
        # Release astroid cache after the request; bounds memory in long-lived server
        if not isinstance(_graph, bool) and _graph is not None:
            try:
                astroid.MANAGER.clear_cache()
            except Exception:  # pragma: no cover
                pass

    return results
