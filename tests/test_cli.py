"""Tests for the CLI entry point, package metadata, and NOTICE."""

from __future__ import annotations

import io
import tomllib
from pathlib import Path

import pytest

from snake_eyes import __version__
from snake_eyes.__main__ import main

ROOT = Path(__file__).resolve().parent.parent


def test_main_missing_flag_prints_usage_and_exits_2() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as exc:
        main([], stdin=io.StringIO(), stdout=stdout, stderr=stderr)
    assert exc.value.code == 2
    assert stderr.getvalue() == "snake-eyes --stdio\n"
    assert stdout.getvalue() == ""


def test_main_stdio_starts_server() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as exc:
        main(["--stdio"], stdin=io.StringIO(""), stdout=stdout, stderr=stderr)
    assert exc.value.code == 0


def test_version_constant() -> None:
    assert __version__ == "0.1.0"


def test_package_metadata() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = data["project"]
    assert project["name"] == "snake-eyes"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.11"
    assert project["license"] == "Apache-2.0"


def test_notice_exact_text() -> None:
    notice = (ROOT / "NOTICE").read_text()
    assert notice == (
        "snake-eyes\n"
        "Copyright 2026 zero-dot-force\n"
        "\n"
        "This product includes software originally developed in gaze-py\n"
        "(https://github.com/mpeter/gaze-py) by Matt Peter, licensed under\n"
        "Apache License 2.0. Copyright headers on lifted files are preserved.\n"
    )
