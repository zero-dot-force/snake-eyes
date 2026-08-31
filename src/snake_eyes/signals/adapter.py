"""Signal adapter: fan out the extractors over analyzed functions.

:func:`extract_signals` is a NEW snake_eyes layer. gaze-py's
``classify/engine.py`` (the scoring engine that turns signals into
``contractual``/``incidental``/``ambiguous`` labels) is deliberately NOT lifted:
Gaze's Go core owns classification scoring, so lifting the engine would
reintroduce drift. snake_eyes emits RAW signals only -- no aggregation, no
clamping, no labels.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from ..analysis import _shared
from ..analysis.detector import analyze_path
from ..analysis.inference import build_caller_index
from ..analysis.models import FunctionRecord
from . import caller, docstring, interface, naming, visibility
from ._types import SignalResult

__all__ = ["extract_signals"]

# source string emitted for each extractor (protocol v1.1.0 vocabulary).
_INTERFACE = "interface"
_VISIBILITY = "visibility"
_CALLER_COUNT = "caller_count"
_NAMING = "naming_convention"
_DOCSTRING = "docstring"


@dataclass(frozen=True)
class _FileContext:
    """Per-file AST-derived inputs the extractors need but FunctionRecord lacks."""

    exported: set[str] = field(default_factory=set)
    class_bases_by_line: dict[int, tuple[str, ...]] = field(default_factory=dict)
    docstring_by_line: dict[int, str | None] = field(default_factory=dict)


_EMPTY_CTX = _FileContext()


def extract_signals(
    root_path: str, patterns: list[str] | None
) -> list[dict[str, object]]:
    """Return raw classification signals for every function under ``root_path``.

    One deterministic file set (``_shared.ordered_file_list(root_path,
    patterns)``) feeds both the AST re-parse (for class bases, docstrings, and
    ``__all__`` membership that ``FunctionRecord`` does not carry) and the
    single :func:`build_caller_index` call. Every non-``None`` extractor result
    becomes exactly one signal dict tagged with the effect's ``side_effect_type``.
    """
    records = analyze_path(root_path, patterns)
    if not records:
        return []

    rel_paths = _shared.ordered_file_list(root_path, patterns)
    file_ctx = _collect_file_context(root_path, rel_paths)
    index = build_caller_index(root_path, patterns)

    signals: list[dict[str, object]] = []
    for record in records:
        ctx = file_ctx.get(record.file, _EMPTY_CTX)
        class_bases = ctx.class_bases_by_line.get(record.line)
        func_doc = ctx.docstring_by_line.get(record.line)
        in_all = record.name in ctx.exported
        caller_count = index.count(record.package, record.name)
        for effect in record.side_effects:
            et = effect.type
            _emit(signals, record, et, _INTERFACE, interface.extract(class_bases))
            _emit(
                signals,
                record,
                et,
                _VISIBILITY,
                visibility.extract(record.name, in_all),
            )
            _emit(signals, record, et, _CALLER_COUNT, caller.extract(caller_count))
            _emit(signals, record, et, _NAMING, naming.extract(record.name, et))
            _emit(signals, record, et, _DOCSTRING, docstring.extract(func_doc, et))

    signals.sort(
        key=lambda s: (
            str(s["package"]),
            str(s["function"]),
            str(s["side_effect_type"]),
            str(s["source"]),
        )
    )
    return signals


def _emit(
    out: list[dict[str, object]],
    record: FunctionRecord,
    side_effect_type: str,
    source: str,
    result: SignalResult | None,
) -> None:
    if result is None:
        return
    out.append(
        {
            "function": record.name,
            "package": record.package,
            "side_effect_type": side_effect_type,
            "source": source,
            "weight": result.weight,
            "reasoning": result.reasoning,
        }
    )


def _collect_file_context(
    root_path: str, rel_paths: list[str]
) -> dict[str, _FileContext]:
    ctx_by_file: dict[str, _FileContext] = {}
    for rel_path, _source, tree in _shared.iter_source_files(root_path, rel_paths):
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        class_bases_by_line: dict[int, tuple[str, ...]] = {}
        docstring_by_line: dict[int, str | None] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                docstring_by_line[node.lineno] = ast.get_docstring(node)
                enclosing = _enclosing_class(node, parents)
                if enclosing is not None:
                    class_bases_by_line[node.lineno] = _class_base_names(enclosing)

        ctx_by_file[rel_path] = _FileContext(
            exported=_extract_all(tree),
            class_bases_by_line=class_bases_by_line,
            docstring_by_line=docstring_by_line,
        )
    return ctx_by_file


def _enclosing_class(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> ast.ClassDef | None:
    """Nearest enclosing class, or ``None`` if ``node`` is a nested function."""
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.ClassDef):
            return cur
        if isinstance(cur, ast.FunctionDef | ast.AsyncFunctionDef):
            return None
        cur = parents.get(cur)
    return None


def _class_base_names(classdef: ast.ClassDef) -> tuple[str, ...]:
    names: list[str] = []
    for base in classdef.bases:
        name = _expr_name(base)
        if name is not None:
            names.append(name)
    for keyword in classdef.keywords:
        if keyword.arg == "metaclass":
            name = _expr_name(keyword.value)
            if name is not None:
                names.append(name)
    return tuple(names)


def _expr_name(expr: ast.expr) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def _extract_all(tree: ast.Module) -> set[str]:
    exported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            continue
        value = node.value
        if isinstance(value, ast.List | ast.Tuple):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    exported.add(elt.value)
    return exported
