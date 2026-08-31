"""Tests for the astroid-backed caller index (analysis/inference.py)."""

from __future__ import annotations

from pathlib import Path

import astroid
import pytest
from astroid.exceptions import AstroidError

from snake_eyes.analysis import inference
from snake_eyes.analysis.inference import build_caller_index, count_callers


def _write(root: Path, rel: str, code: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)


def test_build_caller_index_counts_intra_module_calls(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "mod.py",
        "def target():\n"
        "    return 1\n\n"
        "def c1():\n"
        "    return target()\n\n"
        "def c2():\n"
        "    return target()\n",
    )
    index = build_caller_index(str(tmp_path), None)
    assert index.count("mod", "target") == 2


def test_count_callers_wrapper(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "mod.py",
        "def target():\n    return 1\n\ndef c1():\n    return target()\n",
    )
    assert count_callers(str(tmp_path), "mod", "target") == 1


def test_uncalled_function_returns_zero(tmp_path: Path) -> None:
    _write(tmp_path, "mod.py", "def target():\n    return 1\n")
    assert build_caller_index(str(tmp_path), None).count("mod", "target") == 0


def test_astroid_failure_degrades_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(
        tmp_path,
        "mod.py",
        "def target():\n    return 1\n\ndef c1():\n    return target()\n",
    )

    def boom(*args: object, **kwargs: object) -> object:
        raise AstroidError("boom")

    monkeypatch.setattr(astroid.MANAGER, "ast_from_file", boom)
    index = build_caller_index(str(tmp_path), None)
    assert index.count("mod", "target") == 0


def test_cross_module_call_under_src_layout(tmp_path: Path) -> None:
    _write(tmp_path, "src/pkg/__init__.py", "")
    _write(tmp_path, "src/pkg/b.py", "def target():\n    return 1\n")
    _write(
        tmp_path,
        "src/pkg/a.py",
        "from src.pkg.b import target\n\ndef caller():\n    return target()\n",
    )
    index = build_caller_index(str(tmp_path), None)
    assert index.count("src.pkg.b", "target") >= 1


def test_oversized_file_skipped_before_astroid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(
        tmp_path,
        "mod.py",
        "def target():\n    return 1\n\ndef c1():\n    return target()\n",
    )
    monkeypatch.setattr(inference._shared, "is_analyzable_file", lambda *a, **k: False)

    def fail(*args: object, **kwargs: object) -> object:
        raise AssertionError("astroid must not parse a skipped (oversized) file")

    monkeypatch.setattr(astroid.MANAGER, "ast_from_file", fail)
    index = build_caller_index(str(tmp_path), None)
    assert index.count("mod", "target") == 0
