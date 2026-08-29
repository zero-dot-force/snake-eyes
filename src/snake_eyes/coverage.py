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
    """
    try:
        st = abs_path.stat()
    except OSError as exc:
        print(
            f"snake-eyes/coverage: skipping {rel_path}: stat failed: {exc}",
            file=sys.stderr,
        )
        return None

    if not stat.S_ISREG(st.st_mode):
        print(
            f"snake-eyes/coverage: skipping {rel_path}: not a regular file",
            file=sys.stderr,
        )
        return None

    if st.st_size > MAX_FILE_BYTES:
        print(
            f"snake-eyes/coverage: skipping {rel_path}: size {st.st_size}"
            f" exceeds cap {MAX_FILE_BYTES}",
            file=sys.stderr,
        )
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


def _coverage_entry(
    rel_path: str,
    func_name: str,
    start_line: int,
    end_line: int,
    executed: set[int],
    total_stmts_in_span: int,
) -> dict[str, Any]:
    covered = sum(1 for ln in executed if start_line <= ln <= end_line)
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
    except (OSError, json.JSONDecodeError, MemoryError) as exc:
        print(
            f"snake-eyes/coverage: coverage.json parse error: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        files_map = data["files"]
        if not isinstance(files_map, dict):
            return None
    except (KeyError, TypeError):
        return None

    entries: list[dict[str, Any]] = []

    for key, file_data in files_map.items():
        # Confinement: resolve and check within root
        abs_candidate = _confine_path(key, root)
        if abs_candidate is None:
            continue
        # Normalize to root-relative POSIX
        try:
            rel_path = abs_candidate.relative_to(root).as_posix()
        except ValueError:
            continue

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

        # Build function spans
        spans = _parse_source_spans(abs_candidate, rel_path)
        if spans is None:
            continue

        for func_name, start_line, end_line in spans:
            stmts_in_span = sum(1 for ln in all_stmts if start_line <= ln <= end_line)
            entries.append(
                _coverage_entry(
                    rel_path,
                    func_name,
                    start_line,
                    end_line,
                    executed,
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
        cov = coverage_pkg.Coverage(data_file=str(dot_cov_path))
        cov.load()
    except (
        sqlite3.DatabaseError,
        coverage_pkg.exceptions.CoverageException,
        OSError,
    ) as exc:
        print(
            f"snake-eyes/coverage: .coverage load error: {exc}",
            file=sys.stderr,
        )
        return None

    entries: list[dict[str, Any]] = []

    for rel_path in discovered:
        abs_candidate = root / rel_path

        # Guard: stat + S_ISREG before any open()/analysis2() to prevent blocking
        # on non-regular files (FIFOs, devices, sockets).  Constitution V / D13.
        try:
            st = abs_candidate.stat()
        except OSError as exc:
            print(
                f"snake-eyes/coverage: skipping {rel_path}: stat failed: {exc}",
                file=sys.stderr,
            )
            continue

        if not stat.S_ISREG(st.st_mode):
            print(
                f"snake-eyes/coverage: skipping {rel_path}: not a regular file",
                file=sys.stderr,
            )
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

        # Build function spans
        spans = _parse_source_spans(abs_candidate, rel_path)
        if spans is None:
            continue

        for func_name, start_line, end_line in spans:
            stmts_in_span = sum(
                1 for ln in all_stmts_set if start_line <= ln <= end_line
            )
            entries.append(
                _coverage_entry(
                    rel_path,
                    func_name,
                    start_line,
                    end_line,
                    executed_set,
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

    if json_path.is_file():
        entries = _parse_coverage_json(json_path, root, discovered_set)
    elif dot_cov_path.is_file():
        entries = _parse_dot_coverage(dot_cov_path, root, discovered_set)

    if entries is None:
        return []

    # Deterministic ordering: (file, start_line, function)
    entries.sort(key=lambda e: (e["file"], e["start_line"], e["function"]))
    return entries
