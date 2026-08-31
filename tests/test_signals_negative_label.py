"""Guard: the signal extractors never emit a classification label.

snake-eyes emits RAW signals only. The Gaze Go core owns classification
(contractual / incidental / ambiguous). This test scans the production
``signals`` package for those tokens appearing as *assigned or emitted string
values* (an AST-based scan, so the words remain permitted inside comments that
forbid them).
"""

from __future__ import annotations

import ast
from pathlib import Path

SIGNALS_DIR = Path(__file__).resolve().parents[1] / "src" / "snake_eyes" / "signals"
FORBIDDEN = ("contractual", "incidental", "ambiguous")


def test_signals_package_has_no_classification_labels() -> None:
    py_files = sorted(SIGNALS_DIR.glob("*.py"))
    assert py_files, "expected the signals package to contain modules"
    for py_file in py_files:
        tree = ast.parse(py_file.read_text())
        # Docstrings and bare string-expression statements are documentation
        # (like comments) and may name the forbidden labels in order to forbid
        # them. Only assigned or emitted string *values* are disallowed, so we
        # exclude the string Constants that back an Expr statement.
        doc_constants = {
            id(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in doc_constants
            ):
                lowered = node.value.lower()
                for word in FORBIDDEN:
                    assert word not in lowered, (
                        f"{py_file.name}: forbidden classification label "
                        f"{word!r} appears as a string value"
                    )
