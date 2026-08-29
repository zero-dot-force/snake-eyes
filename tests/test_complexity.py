"""Tests for complexity.compute_complexity.

validates: gaze analyzer protocol v1.1.0
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from snake_eyes.analysis.complexity import compute_complexity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write *files* (rel_path -> content) under *tmp_path* and return it."""
    for rel, content in files.items():
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures" / "effects"


# ---------------------------------------------------------------------------
# 7.1 — exact McCabe integer (hand-derived: base 1 + if + elif + and = 4)
# ---------------------------------------------------------------------------


def test_branchy_complexity(tmp_path: Path) -> None:
    """branchy() in complexity_fixture.py must have complexity 4 (hand-derived)."""
    src = FIXTURES / "complexity_fixture.py"
    dest = tmp_path / "complexity_fixture.py"
    shutil.copy(src, dest)

    entries = compute_complexity(str(tmp_path), None)

    branchy = [e for e in entries if e["name"] == "branchy"]
    assert branchy, "branchy() not found"
    assert branchy[0]["complexity"] == 4, (  # hand-derived: base1+if+elif+and
        f"Expected 4, got {branchy[0]['complexity']}"
    )


def test_nested_function_entries(tmp_path: Path) -> None:
    """Nested functions each get their own entry."""
    src = FIXTURES / "complexity_fixture.py"
    dest = tmp_path / "complexity_fixture.py"
    shutil.copy(src, dest)

    entries = compute_complexity(str(tmp_path), None)

    names = [e["name"] for e in entries]
    assert "nested_outer" in names
    assert "nested_inner" in names


def test_lambda_excluded(tmp_path: Path) -> None:
    """Lambda expressions must NOT appear as entries."""
    code = "f = lambda x: x + 1\ndef real_func(): return f(1)\n"
    (tmp_path / "lam.py").write_text(code)

    entries = compute_complexity(str(tmp_path), None)

    assert all(e["name"] != "<lambda>" for e in entries)
    assert any(e["name"] == "real_func" for e in entries)


def test_package_derivation(tmp_path: Path) -> None:
    """Package is derived from the root-relative POSIX path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("def init_func(): pass\n")
    (pkg / "sub.py").write_text("def sub_func(): pass\n")

    entries = compute_complexity(str(tmp_path), None)

    by_name = {e["name"]: e for e in entries}
    assert by_name["init_func"]["package"] == "mypkg"
    assert by_name["sub_func"]["package"] == "mypkg.sub"


def test_syntax_error_skipped_no_crash(tmp_path: Path) -> None:
    """syntax_error.py is skipped; valid files still return results."""
    shutil.copy(FIXTURES / "syntax_error.py", tmp_path / "syntax_error.py")
    (tmp_path / "valid.py").write_text("def ok(): pass\n")

    entries = compute_complexity(str(tmp_path), None)

    names = [e["name"] for e in entries]
    assert "ok" in names, "valid file must still be analysed"


def test_ordering_by_file_line_name(tmp_path: Path) -> None:
    """Entries are ordered by (file, line, name)."""
    code = "def b(): pass\ndef a(): pass\n"
    (tmp_path / "mod.py").write_text(code)

    entries = compute_complexity(str(tmp_path), None)

    assert entries == sorted(entries, key=lambda e: (e["file"], e["line"], e["name"]))


def test_byte_identical_determinism(tmp_path: Path) -> None:
    """Two runs over the same tree produce byte-identical JSON."""
    import json

    shutil.copy(FIXTURES / "complexity_fixture.py", tmp_path / "complexity_fixture.py")
    (tmp_path / "valid.py").write_text("def ok(): pass\n")

    run1 = json.dumps(compute_complexity(str(tmp_path), None), sort_keys=True)
    run2 = json.dumps(compute_complexity(str(tmp_path), None), sort_keys=True)
    assert run1 == run2


def test_missing_root_raises(tmp_path: Path) -> None:
    """Non-existent root_path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        compute_complexity(str(tmp_path / "no_such_dir"), None)
