"""Caller-count inference for the ``classify_signals`` capability.

This module builds an inbound-call index for a Python project using
`astroid <https://github.com/pylint-dev/astroid>`_ static inference. It is a
snake_eyes original (not lifted from gaze-py): gaze-py counts callers against
its own project model, whereas snake_eyes uses astroid for Python name
resolution per the Python-Native Analysis principle.

Constitution V (Analysis Safety) guarantees enforced here:

* **Static only** -- astroid parses source files from disk; the analyzed
  project is never imported or executed.
* **Byte-cap** -- files are filtered through
  :func:`snake_eyes.analysis._shared.is_analyzable_file` (16 MiB cap plus a
  regular-file check) *before* astroid parses them. The astroid path does not
  use :func:`_shared.iter_source_files`, so it applies that guard explicitly.
* **Isolation** -- an isolated per-request manager cache is used so that a
  prior request over a different tree cannot contaminate this one in the
  long-lived stdio server.
* **On-disk resolution** -- callees are only counted when they resolve to a
  file within the analyzed set, so ambient ``site-packages`` are never
  consulted.
* **Graceful degradation** -- any astroid/resource failure degrades the whole
  index to empty (counts of zero); a single uninferable call site is skipped.
"""

from __future__ import annotations

import pathlib
from collections import defaultdict

import astroid  # type: ignore[import-untyped]
from astroid import nodes
from astroid.exceptions import (  # type: ignore[import-untyped]
    AstroidError,
    InferenceError,
)
from astroid.util import Uninferable  # type: ignore[import-untyped]

from . import _shared

__all__ = ["CallerIndex", "build_caller_index", "count_callers"]

# Any of these during the astroid build/inference degrades the affected count
# to zero rather than propagating to the RPC layer (Constitution V). Mirrors the
# broadened tuple the #4 ``ast`` path uses for the same reason.
_DEGRADE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AstroidError,
    InferenceError,
    RecursionError,
    MemoryError,
    OSError,
)


def _normalize(path: str) -> str:
    """Resolve ``path`` to a canonical absolute string for stable matching."""
    return str(pathlib.Path(path).resolve())


class CallerIndex:
    """Inbound-call counts keyed by ``(defining file, function name)``.

    Built once per ``extract_signals`` invocation and reused for every lookup;
    :meth:`count` performs no astroid work.
    """

    def __init__(
        self,
        counts: dict[tuple[str, str], int],
        module_to_file: dict[str, str],
    ) -> None:
        self._counts = counts
        self._module_to_file = module_to_file

    def count(self, module: str, func_name: str) -> int:
        """Return inbound calls to ``func_name`` defined in dotted ``module``.

        Matching is by resolved defining file path (robust to ``src/`` layouts),
        not dotted-module-string equality. Returns ``0`` when unknown.
        """
        file = self._module_to_file.get(module)
        if file is None:
            return 0
        return self._counts.get((file, func_name), 0)


def _empty_index() -> CallerIndex:
    return CallerIndex({}, {})


def build_caller_index(root_path: str, patterns: list[str] | None) -> CallerIndex:
    """Build the per-request inbound-call index over the on-disk project.

    Enumerates the same file set as discovery via
    :func:`_shared.ordered_file_list`, filters through
    :func:`_shared.is_analyzable_file` (byte-cap) before astroid parses, and
    resolves callees only within the analyzed file set. Any astroid or
    resource-exhaustion failure degrades the whole index to empty.
    """
    rel_paths = _shared.ordered_file_list(root_path, patterns)
    root = pathlib.Path(root_path)
    try:
        return _build(root, rel_paths)
    except _DEGRADE_EXCEPTIONS:
        return _empty_index()


def _build(root: pathlib.Path, rel_paths: list[str]) -> CallerIndex:
    manager = astroid.MANAGER
    # Isolated per-request state: drop cached modules so a prior request on a
    # different tree cannot leak into this one (the stdio server is long-lived).
    manager.clear_cache()

    analyzed_files: set[str] = set()
    module_to_file: dict[str, str] = {}
    modules: list[nodes.Module] = []

    for rel in rel_paths:
        abs_path = root / rel
        if not _shared.is_analyzable_file(abs_path, label="classify_signals"):
            continue
        modname = _shared.derive_package(rel)
        try:
            module = manager.ast_from_file(str(abs_path), modname, source=True)
        except _DEGRADE_EXCEPTIONS:
            continue
        norm = _normalize(str(abs_path))
        analyzed_files.add(norm)
        module_to_file[modname] = norm
        modules.append(module)

    counts: dict[tuple[str, str], int] = defaultdict(int)
    for module in modules:
        for call in module.nodes_of_class(nodes.Call):
            target = _resolve_call_target(call, analyzed_files)
            if target is not None:
                counts[target] += 1
    return CallerIndex(dict(counts), module_to_file)


def _resolve_call_target(
    call: nodes.Call, analyzed_files: set[str]
) -> tuple[str, str] | None:
    """Resolve a call's callee to ``(defining_file, func_name)`` if in-project.

    A callee that resolves to :data:`astroid.util.Uninferable` (or raises during
    inference) is skipped so counting continues for the remaining call sites.
    """
    try:
        inferred = list(call.func.infer())
    except _DEGRADE_EXCEPTIONS:
        return None
    for candidate in inferred:
        if candidate is Uninferable:
            continue
        if not isinstance(candidate, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
            continue
        file = getattr(candidate.root(), "file", None)
        if file is None:
            continue
        norm = _normalize(file)
        if norm in analyzed_files:
            return (norm, candidate.name)
    return None


def count_callers(
    root_path: str,
    module: str,
    func_name: str,
    patterns: list[str] | None = None,
) -> int:
    """Thin, test-only convenience wrapper around :func:`build_caller_index`.

    Builds a one-off index then performs a single lookup, so it rebuilds the
    whole index per call. It MUST NOT be used on the per-function adapter hot
    path -- build the index once with :func:`build_caller_index` and reuse
    :meth:`CallerIndex.count`.
    """
    return build_caller_index(root_path, patterns).count(module, func_name)
