"""Tests for file and test discovery."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from snake_eyes.discovery import DiscoveryResult, discover


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_splits_source_and_test_files(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "foo.py")
    _write(tmp_path / "tests" / "test_foo.py")
    result = discover(str(tmp_path))
    assert result.source_files == ("src/foo.py",)
    assert result.test_files == ("tests/test_foo.py",)


def test_test_prefix_at_root(tmp_path: Path) -> None:
    _write(tmp_path / "test_foo.py")
    result = discover(str(tmp_path))
    assert result.source_files == ()
    assert result.test_files == ("test_foo.py",)


def test_test_suffix(tmp_path: Path) -> None:
    _write(tmp_path / "foo_test.py")
    result = discover(str(tmp_path))
    assert result.source_files == ()
    assert result.test_files == ("foo_test.py",)


def test_test_directory_component(tmp_path: Path) -> None:
    _write(tmp_path / "test" / "helper.py")
    result = discover(str(tmp_path))
    assert result.source_files == ()
    assert result.test_files == ("test/helper.py",)


def test_venv_and_pycache_excluded(tmp_path: Path) -> None:
    _write(tmp_path / ".venv" / "lib" / "site.py")
    _write(tmp_path / "__pycache__" / "x.py")
    _write(tmp_path / "a.py")
    result = discover(str(tmp_path))
    assert result.source_files == ("a.py",)
    assert result.test_files == ()


def test_egg_info_excluded(tmp_path: Path) -> None:
    _write(tmp_path / "myproj.egg-info" / "x.py")
    _write(tmp_path / "a.py")
    result = discover(str(tmp_path))
    assert result.source_files == ("a.py",)


def test_pyi_excluded(tmp_path: Path) -> None:
    _write(tmp_path / "a.py")
    _write(tmp_path / "a.pyi")
    result = discover(str(tmp_path))
    assert result.source_files == ("a.py",)


def test_empty_project(tmp_path: Path) -> None:
    result = discover(str(tmp_path))
    assert result == DiscoveryResult((), ())


def test_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover(str(tmp_path / "nope"))


def test_non_directory_root_raises(tmp_path: Path) -> None:
    target = tmp_path / "file.py"
    target.write_text("")
    with pytest.raises(FileNotFoundError):
        discover(str(target))


def test_directory_pattern_restricts_to_subtree(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "foo.py")
    _write(tmp_path / "tests" / "test_foo.py")
    result = discover(str(tmp_path), ["src"])
    assert result.source_files == ("src/foo.py",)
    assert result.test_files == ()


def test_trailing_slash_directory_pattern(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "foo.py")
    _write(tmp_path / "tests" / "test_foo.py")
    result = discover(str(tmp_path), ["src/"])
    assert result.source_files == ("src/foo.py",)
    assert result.test_files == ()


def test_glob_pattern_matches_relative_to_root(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "foo.py")
    _write(tmp_path / "tests" / "test_foo.py")
    result = discover(str(tmp_path), ["**/*.py"])
    assert result.source_files == ("src/foo.py",)
    assert result.test_files == ("tests/test_foo.py",)


def test_whole_tree_patterns(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "a.py")
    _write(tmp_path / "tests" / "test_a.py")
    for pattern in (["./..."], ["..."]):
        result = discover(str(tmp_path), pattern)
        assert result.source_files == ("src/a.py",)
        assert result.test_files == ("tests/test_a.py",)


def test_empty_patterns_walk_whole_tree(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "a.py")
    result = discover(str(tmp_path), [])
    assert result.source_files == ("src/a.py",)


def test_prefix_recursive_pattern(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "a.py")
    _write(tmp_path / "tests" / "test_a.py")
    result = discover(str(tmp_path), ["src/..."])
    assert result.source_files == ("src/a.py",)
    assert result.test_files == ()


def test_results_are_sorted(tmp_path: Path) -> None:
    _write(tmp_path / "b.py")
    _write(tmp_path / "a.py")
    _write(tmp_path / "tests" / "c_test.py")
    result = discover(str(tmp_path))
    assert result.source_files == ("a.py", "b.py")
    assert result.test_files == ("tests/c_test.py",)


def test_file_symlink_skipped(tmp_path: Path) -> None:
    _write(tmp_path / "a.py")
    os.symlink(tmp_path / "a.py", tmp_path / "link.py")
    result = discover(str(tmp_path))
    assert result.source_files == ("a.py",)


def test_directory_symlink_not_followed(tmp_path: Path) -> None:
    _write(tmp_path / "real" / "a.py")
    os.symlink(tmp_path / "real", tmp_path / "linkdir")
    result = discover(str(tmp_path))
    assert result.source_files == ("real/a.py",)
