"""File and test discovery for snake-eyes.

Discovers Python source and test files under a project root using the Gaze
``./...`` pattern convention. Results are deterministic: both lists are
returned in sorted lexicographic order by POSIX path.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

# Directory names that are never descended into. ``*.egg-info`` suffixes are
# handled separately in ``_should_prune``.
_EXCLUDE_DIRS = frozenset(
    {
        ".venv",
        "venv",
        "env",
        ".env",
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "dist",
        "build",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "node_modules",
        ".eggs",
    }
)

_WHOLE_TREE_PATTERNS = frozenset({"", ".", "...", "/", "./"})


@dataclass(frozen=True)
class DiscoveryResult:
    """The discovered source and test files, each sorted and POSIX-relative."""

    source_files: tuple[str, ...]
    test_files: tuple[str, ...]


def discover(root_path: str, patterns: list[str] | None = None) -> DiscoveryResult:
    """Discover ``.py`` files under ``root_path`` and classify them.

    ``patterns`` of ``None``/``[]``/``["./..."]``/``["..."]`` walk the whole
    tree. A relative directory pattern (``src`` or ``src/``) walks that
    subtree. A glob pattern (``**/*.py``) is applied relative to root. Raises
    ``FileNotFoundError`` when ``root_path`` is missing or not a directory.
    """
    root = Path(root_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"root_path is not a directory: {root_path}")

    files = _walk(root)
    selected = _select(files, patterns)
    sources, tests = _classify(selected)
    return DiscoveryResult(tuple(sorted(sources)), tuple(sorted(tests)))


def _walk(root: Path) -> list[str]:
    """Walk ``root`` collecting POSIX-relative ``.py`` paths (excluding ``.pyi``).

    Does not descend into excluded directories and skips all symlinks (both
    directory and file).
    """
    found: list[str] = []
    root_str = str(root)
    for dirpath, dirnames, filenames in os.walk(root_str, followlinks=False):
        dirnames[:] = [
            name for name in dirnames if not _should_prune(Path(dirpath) / name)
        ]
        rel_dir = os.path.relpath(dirpath, root_str)
        for filename in filenames:
            if filename.endswith(".pyi") or not filename.endswith(".py"):
                continue
            full = Path(dirpath) / filename
            if full.is_symlink():
                continue
            rel = filename if rel_dir == "." else os.path.join(rel_dir, filename)
            found.append(rel.replace(os.sep, "/"))
    return found


def _should_prune(path: Path) -> bool:
    """Return ``True`` for excluded directories and directory symlinks."""
    if path.name in _EXCLUDE_DIRS:
        return True
    if path.name.endswith(".egg-info"):
        return True
    if path.is_symlink():
        return True
    return False


def _select(files: list[str], patterns: list[str] | None) -> list[str]:
    """Return the files matching the given patterns (or all files)."""
    if not patterns:
        return files
    return [f for f in files if any(_matches(f, pattern) for pattern in patterns)]


def _matches(relpath: str, pattern: str) -> bool:
    """Return ``True`` when ``relpath`` matches a single pattern.

    Reduces Go's ``./pkg/...`` semantics to "directory prefix + recursive":
    ``...``/``./...`` matches everything; ``prefix/...`` matches the subtree;
    a plain directory matches its subtree; a glob matches via ``fnmatch``.
    """
    normalized = pattern[2:] if pattern.startswith("./") else pattern
    if normalized in _WHOLE_TREE_PATTERNS:
        return True
    if normalized.endswith("/..."):
        return relpath.startswith(normalized[:-4].rstrip("/") + "/")
    if any(ch in normalized for ch in "*?["):
        return fnmatch.fnmatchcase(relpath, normalized)
    return relpath.startswith(normalized.rstrip("/") + "/")


def _classify(files: list[str]) -> tuple[list[str], list[str]]:
    """Split files into source and test lists (disjoint; test wins)."""
    sources: list[str] = []
    tests: list[str] = []
    for relpath in files:
        if _is_test(relpath):
            tests.append(relpath)
        else:
            sources.append(relpath)
    return sources, tests


def _is_test(relpath: str) -> bool:
    """Classify a POSIX-relative path as a test file.

    A file is a test if its filename starts with ``test_``, ends with
    ``_test.py``, or any directory component is ``tests`` or ``test``.
    """
    parts = relpath.split("/")
    filename = parts[-1]
    if filename.startswith("test_"):
        return True
    if filename.endswith("_test.py"):
        return True
    return any(part in ("tests", "test") for part in parts[:-1])
