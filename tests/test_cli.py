"""Tests for the CLI entry point, package metadata, and NOTICE."""

from __future__ import annotations

import importlib.metadata
import io
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from conftest import req

from snake_eyes import __version__
from snake_eyes.__main__ import main

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("args", [[], ["--verbose"], ["--stdio", "--stdio"]])
def test_main_without_stdio_flag_prints_usage_and_exits_2(args: list[str]) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as exc:
        main(args, stdin=io.StringIO(), stdout=stdout, stderr=stderr)
    assert exc.value.code == 2
    assert stderr.getvalue() == "snake-eyes --stdio\n"
    assert stdout.getvalue() == ""


def test_main_stdio_starts_server() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as exc:
        main(
            ["--stdio"],
            stdin=io.StringIO(req("initialize", root_path="/abs") + "\n"),
            stdout=stdout,
            stderr=stderr,
        )
    assert exc.value.code == 0
    response = json.loads(stdout.getvalue().splitlines()[0])
    assert response["result"]["analyzer_name"] == "snake-eyes"


def test_main_usage_uses_real_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_err)
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert fake_err.getvalue() == "snake-eyes --stdio\n"


def test_main_stdio_reconfigures_real_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_stdin = io.TextIOWrapper(
        io.BytesIO(req("shutdown", id=1).encode() + b"\n"), encoding="ascii"
    )
    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    with pytest.raises(SystemExit) as exc:
        main(["--stdio"])
    assert exc.value.code == 0
    assert fake_stdin.encoding == "utf-8"
    assert fake_stdout.encoding == "utf-8"
    fake_stdout.flush()
    wire = fake_stdout.buffer.getvalue().decode("utf-8")
    assert json.loads(wire.splitlines()[0]) == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_version_constant() -> None:
    assert __version__ == "0.1.0"


def test_version_is_single_sourced() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = data["project"]
    assert "version" in project["dynamic"]
    assert data["tool"]["hatch"]["version"]["path"] == "src/snake_eyes/__init__.py"
    assert importlib.metadata.version("snake-eyes") == __version__


def test_package_metadata() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = data["project"]
    assert project["name"] == "snake-eyes"
    assert project["requires-python"] == ">=3.11"
    assert project["license"] == "Apache-2.0"
    assert project["scripts"]["snake-eyes"] == "snake_eyes.__main__:main"


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


def test_subprocess_initialize_shutdown_roundtrip() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "snake_eyes", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    init = req("initialize", root_path="/abs")
    shutdown = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "shutdown"})
    out, _ = proc.communicate(init + "\n" + shutdown + "\n", timeout=10)
    lines = out.splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["result"]["analyzer_name"] == "snake-eyes"
    assert json.loads(lines[1]) == {"jsonrpc": "2.0", "id": 2, "result": {}}
    assert proc.returncode == 0


def test_subprocess_without_flag_exits_2() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "snake_eyes"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr == "snake-eyes --stdio\n"
