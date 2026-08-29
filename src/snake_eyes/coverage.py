"""Coverage data parser for snake-eyes.

Reads existing coverage data (``coverage.json`` or ``.coverage``) and maps
executed/missing lines to function spans via AST analysis.

This module NEVER runs the analyzed project's tests or invokes ``coverage run``.
It reads data files only.

Public API: ``parse_coverage(root_path, patterns) -> list[dict]``

NOTE: ``import coverage`` resolves to the third-party coverage package because
Python 3 uses absolute imports by default; the package name (``coverage``)
differs from this module's dotted path (``snake_eyes.coverage``).
"""

from __future__ import annotations

import ast
import bisect
import json
import pathlib
import sqlite3
import stat
import sys
from typing import Any

import coverage as coverage_pkg

from .analysis._shared import (
    BROADENED_EXCEPTIONS,
    MAX_FILE_BYTES,
    enumerate_functions_with_spans,
    is_analyzable_file,
    ordered_file_list,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_source_spans(
    abs_path: pathlib.Path,
    rel_path: str,
) -> list[tuple[str, int, int]] | None:
    """Return ``[(name, start_line, end_line), ...]`` for *abs_path*.

    Returns ``None`` when the file should be skipped (non-regular, over-cap,
    or parse error).  Diagnostics go to stderr.

    Uses the centralised ``is_analyzable_file`` guard (Constitution V / H1).
    """
    # Centralised stat + S_ISREG + byte-cap guard — no duplication.
    if not is_analyzable_file(abs_path, label=f"snake-eyes/coverage: {rel_path}"):
        return None

    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(abs_path))
    except BROADENED_EXCEPTIONS as exc:
        print(
            f"snake-eyes/coverage: skipping {rel_path}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        spans = enumerate_functions_with_spans(tree)
    except BROADENED_EXCEPTIONS as exc:
        print(
            f"snake-eyes/coverage: skipping {rel_path}: traversal error: {exc}",
            file=sys.stderr,
        )
        return None

    return spans


def _count_in_span(sorted_lines: list[int], start_line: int, end_line: int) -> int:
    """Count elements in *sorted_lines* within [start_line, end_line] in O(log S)."""
    lo = bisect.bisect_left(sorted_lines, start_line)
    hi = bisect.bisect_right(sorted_lines, end_line)
    return hi - lo


def _coverage_entry(
    rel_path: str,
    func_name: str,
    start_line: int,
    end_line: int,
    sorted_executed: list[int],
    total_stmts_in_span: int,
) -> dict[str, Any]:
    covered = _count_in_span(sorted_executed, start_line, end_line)
    total = total_stmts_in_span
    pct = round(covered / total * 100, 1) if total > 0 else 0.0
    return {
        "file": rel_path,
        "function": func_name,
        "start_line": start_line,
        "end_line": end_line,
        "covered_stmts": covered,
        "total_stmts": total,
        "percentage": pct,
    }


def _confine_path(key: str, root: pathlib.Path) -> pathlib.Path | None:
    """Return the resolved path iff it is within *root*, else None."""
    try:
        candidate = (root / key).resolve()
        candidate.relative_to(root)  # raises ValueError if outside root
        return candidate
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# JSON branch
# ---------------------------------------------------------------------------


def _parse_coverage_json(
    json_path: pathlib.Path,
    root: pathlib.Path,
    discovered: set[str],
) -> list[dict[str, Any]] | None:
    """Parse ``coverage.json`` and return entries or ``None`` on whole-file error."""
    try:
        st = json_path.stat()
        if st.st_size > MAX_FILE_BYTES:
            print(
                f"snake-eyes/coverage: coverage.json size {st.st_size} exceeds"
                f" cap {MAX_FILE_BYTES}; skipping",
                file=sys.stderr,
            )
            return []
        raw = json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, MemoryError, RecursionError) as exc:
        print(
            f"snake-eyes/coverage: coverage.json parse error: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        files_map = data["files"]
        if not isinstance(files_map, dict):
            # M9: non-dict 'files' value → graceful degradation to [] (not None)
            return []
    except (KeyError, TypeError):
        return None

    entries: list[dict[str, Any]] = []

    for key, file_data in files_map.items():
        # Confinement: resolve and check within root
        abs_candidate = _confine_path(key, root)
        if abs_candidate is None:
            continue
        # Normalize to root-relative POSIX.
        # _confine_path guarantees containment, so relative_to always succeeds.
        rel_path = abs_candidate.relative_to(root).as_posix()

        # Only process discovered files
        if rel_path not in discovered:
            continue

        # Shape validation
        try:
            if not isinstance(file_data, dict):
                continue
            executed_lines_raw = file_data["executed_lines"]
            missing_lines_raw = file_data["missing_lines"]
            if not isinstance(executed_lines_raw, list) or not isinstance(
                missing_lines_raw, list
            ):
                continue
        except (KeyError, TypeError):
            continue

        try:
            executed: set[int] = set(int(ln) for ln in executed_lines_raw)
            missing: set[int] = set(int(ln) for ln in missing_lines_raw)
        except (ValueError, TypeError):
            # JSON-valid but wrong-shape list (e.g. non-int elements): skip this file
            continue
        all_stmts: set[int] = executed | missing

        # Sort once per file for O(log S) bisect counting (M5).
        sorted_executed = sorted(executed)
        sorted_all_stmts = sorted(all_stmts)

        # Build function spans
        spans = _parse_source_spans(abs_candidate, rel_path)
        if spans is None:
            continue

        for func_name, start_line, end_line in spans:
            stmts_in_span = _count_in_span(sorted_all_stmts, start_line, end_line)
            entries.append(
                _coverage_entry(
                    rel_path,
                    func_name,
                    start_line,
                    end_line,
                    sorted_executed,
                    stmts_in_span,
                )
            )

    return entries


# ---------------------------------------------------------------------------
# .coverage (SQLite) branch
# ---------------------------------------------------------------------------


def _parse_dot_coverage(
    dot_cov_path: pathlib.Path,
    root: pathlib.Path,
    discovered: set[str],
) -> list[dict[str, Any]] | None:
    """Parse a ``.coverage`` data file via the coverage.py API."""
    try:
        # H2: config_file=False prevents auto-discovery of [tool.coverage] /
        # .coveragerc from cwd — non-deterministic + plugin exec (Constitution I,V).
        cov = coverage_pkg.Coverage(data_file=str(dot_cov_path), config_file=False)
        cov.load()
    except (
        sqlite3.DatabaseError,
        coverage_pkg.exceptions.CoverageException,
        OSError,
        MemoryError,
        ValueError,
        RecursionError,
    ) as exc:
        print(
            f"snake-eyes/coverage: .coverage load error: {exc}",
            file=sys.stderr,
        )
        return None

    entries: list[dict[str, Any]] = []

    for rel_path in discovered:
        abs_candidate = root / rel_path

        # Guard: stat + S_ISREG + byte-cap before any analysis2() to prevent
        # blocking on non-regular files and to enforce DoS bound (Constitution V / H1).
        if not is_analyzable_file(abs_candidate, label=rel_path):
            continue

        # analysis2 may raise per-file CoverageException (NoSource, NotPython, etc.)
        try:
            # analysis2 returns (filename, stmts, excluded, missing, misa)
            _fname, stmts, _excluded, missing_stmts, _misa = cov.analysis2(
                str(abs_candidate)
            )
        except (
            SyntaxError,
            ValueError,
            RecursionError,
            OSError,
            MemoryError,
            coverage_pkg.exceptions.CoverageException,
        ) as exc:
            print(
                f"snake-eyes/coverage: skipping {rel_path}: analysis2 error: {exc}",
                file=sys.stderr,
            )
            continue

        executed_set: set[int] = set(stmts) - set(missing_stmts)
        all_stmts_set: set[int] = set(stmts)

        # Sort once per file for O(log S) bisect counting (M5).
        sorted_executed = sorted(executed_set)
        sorted_all_stmts = sorted(all_stmts_set)

        # Build function spans
        spans = _parse_source_spans(abs_candidate, rel_path)
        if spans is None:
            continue

        for func_name, start_line, end_line in spans:
            stmts_in_span = _count_in_span(sorted_all_stmts, start_line, end_line)
            entries.append(
                _coverage_entry(
                    rel_path,
                    func_name,
                    start_line,
                    end_line,
                    sorted_executed,
                    stmts_in_span,
                )
            )

    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_coverage(
    root_path: str,
    patterns: list[str] | None,
) -> list[dict[str, Any]]:
    """Read coverage data and return per-function coverage entries.

    Lookup order: ``root_path/coverage.json`` (stdlib json) then
    ``root_path/.coverage`` (coverage.py API).  Missing data → ``[]``.

    Raises ``FileNotFoundError`` when *root_path* is not a directory
    (caller maps this to -32602 before any file lookup).

    Returns a **bare list** (NOT ``{"functions": [...]}``) — the server handler
    wraps it.

    Result is ordered by ``(file, start_line, function)``.
    """
    root = pathlib.Path(root_path).resolve()

    # ordered_file_list raises FileNotFoundError for non-existent root_path
    # (via discover() internally) — preserves -32602 error mapping.
    files = ordered_file_list(root_path, patterns)
    discovered_set: set[str] = set(files)

    json_path = root / "coverage.json"
    dot_cov_path = root / ".coverage"

    entries: list[dict[str, Any]] | None = None

    # Reject non-regular files (FIFO / device / socket / directory) at the fixed
    # data-file locations so a planted special file cannot hang or mislead the
    # parser. Note: p.stat() follows symlinks (exactly like is_file()), so a
    # symlink to a regular file is still accepted; that is safe because results
    # are confined to discovered files under root via _confine_path(). Graceful:
    # a missing or invalid data file → empty result.
    def _is_regular_file(p: pathlib.Path) -> bool:
        try:
            return stat.S_ISREG(p.stat().st_mode)
        except OSError:
            return False

    if _is_regular_file(json_path):
        entries = _parse_coverage_json(json_path, root, discovered_set)
    elif _is_regular_file(dot_cov_path):
        entries = _parse_dot_coverage(dot_cov_path, root, discovered_set)

    if entries is None:
        return []

    # Deterministic ordering: (file, start_line, function)
    entries.sort(key=lambda e: (e["file"], e["start_line"], e["function"]))
    return entries
