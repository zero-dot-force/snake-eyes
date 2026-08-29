"""Shared helpers for snake-eyes analysis modules.

Provides:
- ``iter_source_files``: safe file reader/enumerator (stat + S_ISREG + byte-cap +
  AST parse with recursion budget); yields ``(rel_path, source, tree)`` tuples.
- ``enumerate_functions_with_spans``: per-function AST walk yielding
  ``(name, start_line, end_line)`` triples for every ``def``/``async def``.
- ``derive_package``: dotted module path from a root-relative POSIX file path.
- ``ordered_file_list``: deterministic ordered concatenation of source_files then
  test_files, de-duplicated preserving first occurrence (never a set union).
- ``is_analyzable_file``: single guard helper — stat + S_ISREG + byte-cap;
  emits a stderr diagnostic and returns ``False`` when the file must be skipped.
"""

from __future__ import annotations

import ast
import pathlib
import stat
import sys
from collections.abc import Iterator

from ..discovery import discover

# ---------------------------------------------------------------------------
# Resource bounds (Constitution V, design D13)
# ---------------------------------------------------------------------------

MAX_FILE_BYTES: int = 16 * 1024 * 1024  # 16 MiB — PRE-open() byte-size cap
MAX_AST_DEPTH: int = 200  # shared recursion budget for all AST visitors

# BROADENED_EXCEPTIONS covers all skip-and-continue conditions across all modules.
BROADENED_EXCEPTIONS: tuple[type[Exception], ...] = (
    SyntaxError,
    ValueError,
    RecursionError,
    OSError,
    MemoryError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def derive_package(rel_path: str) -> str:
    """Return the dotted module path for *rel_path* (root-relative POSIX).

    Examples::

        "pkg/__init__.py"  -> "pkg"
        "pkg/sub/mod.py"   -> "pkg.sub.mod"
        "server.py"        -> "server"
    """
    without_ext = rel_path.removesuffix(".py")
    dotted = without_ext.replace("/", ".")
    if dotted.endswith(".__init__"):
        dotted = dotted[: -len(".__init__")]
    return dotted


def is_analyzable_file(abs_path: pathlib.Path, label: str | None = None) -> bool:
    """Return ``True`` iff *abs_path* is a regular file within the byte-size cap.

    Performs ``stat`` → ``S_ISREG`` → ``st_size > MAX_FILE_BYTES`` checks.
    Emits a one-line ``sys.stderr`` diagnostic and returns ``False`` on any
    skip condition.  *label* overrides the display name (defaults to
    ``str(abs_path)``).

    Constitution V / design D13: centralised guard so no caller re-implements
    the stat + S_ISREG + byte-cap sequence.
    """
    display = label if label is not None else str(abs_path)
    try:
        st = abs_path.stat()
    except OSError as exc:
        print(
            f"snake-eyes: skipping {display}: stat failed: {exc}",
            file=sys.stderr,
        )
        return False

    if not stat.S_ISREG(st.st_mode):
        print(
            f"snake-eyes: skipping {display}: not a regular file",
            file=sys.stderr,
        )
        return False

    if st.st_size > MAX_FILE_BYTES:
        print(
            f"snake-eyes: skipping {display}: file size {st.st_size} exceeds"
            f" cap {MAX_FILE_BYTES}",
            file=sys.stderr,
        )
        return False

    return True


def ordered_file_list(root_path: str, patterns: list[str] | None) -> list[str]:
    """Return the ordered concatenation of source_files then test_files.

    Files are de-duplicated preserving first occurrence (never a set union —
    determinism, Constitution I).  Raises ``FileNotFoundError`` when
    *root_path* is not a directory (caller maps to -32602).
    """
    result = discover(root_path, patterns)
    seen: set[str] = set()
    ordered: list[str] = []
    for rel in list(result.source_files) + list(result.test_files):
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    return ordered


def iter_source_files(
    root_path: str,
    rel_paths: list[str],
) -> Iterator[tuple[str, str, ast.Module]]:
    """Yield ``(rel_path, source, tree)`` for each readable, parseable file.

    Guards applied (in order, all are skip-and-continue):
    1. ``stat`` — skips non-regular files (FIFOs, devices, sockets) with a
       stderr diagnostic before ``open()`` is attempted.
    2. Byte-size cap — derived from ``stat().st_size``; files exceeding
       ``MAX_FILE_BYTES`` are skipped before ``open()``.
    3. ``open()`` + ``read()`` — ``OSError`` is caught and file is skipped.
    4. ``ast.parse`` — ``SyntaxError``, ``ValueError``, ``RecursionError`` are
       caught; file is skipped.
    5. ``MemoryError`` — caught at parse or traversal time; file is skipped.

    A per-file diagnostic is written to ``sys.stderr``; nothing goes to stdout.
    """
    root = pathlib.Path(root_path).resolve()

    for rel in rel_paths:
        abs_path = root / rel
        if not is_analyzable_file(abs_path, label=rel):
            continue

        try:
            source = abs_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(abs_path))
        except BROADENED_EXCEPTIONS as exc:
            print(
                f"snake-eyes: skipping {rel}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue

        yield rel, source, tree


def enumerate_functions_with_spans(
    tree: ast.Module,
) -> list[tuple[str, int, int]]:
    """Return ``[(name, start_line, end_line), ...]`` for every def/async def.

    ``end_lineno`` is provided by Python 3.8+ ast nodes.  Falls back to
    ``start_line`` when not present (should not happen on 3.11+).
    """

    class _SpanLister(ast.NodeVisitor):
        def __init__(self) -> None:
            self.functions: list[tuple[str, int, int]] = []
            self._depth = 0
            self._max_depth = MAX_AST_DEPTH

        def _check_depth(self) -> None:
            if self._depth > self._max_depth:
                raise RecursionError("AST depth budget exceeded in span lister")

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._depth += 1
            self._check_depth()
            end = getattr(node, "end_lineno", node.lineno)
            self.functions.append((node.name, node.lineno, end))
            self.generic_visit(node)
            self._depth -= 1

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._depth += 1
            self._check_depth()
            end = getattr(node, "end_lineno", node.lineno)
            self.functions.append((node.name, node.lineno, end))
            self.generic_visit(node)
            self._depth -= 1

        def visit_Lambda(self, node: ast.Lambda) -> None:
            pass

    lister = _SpanLister()
    lister.visit(tree)
    return lister.functions
