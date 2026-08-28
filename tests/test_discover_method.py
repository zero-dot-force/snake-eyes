"""Tests for the discover JSON-RPC method."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from conftest import req, responses

from snake_eyes.protocol import INVALID_PARAMS, initialize_result
from snake_eyes.server import Server


def _run(raw: str) -> str:
    stdin = io.StringIO(raw)
    stdout = io.StringIO()
    server = Server(stdin, stdout, io.StringIO())
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    return stdout.getvalue()


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_discover_roundtrip(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "foo.py")
    _write(tmp_path / "tests" / "test_foo.py")
    raw = req("discover", root_path=str(tmp_path), patterns=["./..."]) + "\n"
    response = responses(_run(raw))[0]
    assert response["result"] == {
        "source_files": ["src/foo.py"],
        "test_files": ["tests/test_foo.py"],
    }


def test_discover_missing_patterns_ok(tmp_path: Path) -> None:
    _write(tmp_path / "a.py")
    raw = req("discover", root_path=str(tmp_path)) + "\n"
    response = responses(_run(raw))[0]
    assert response["result"] == {"source_files": ["a.py"], "test_files": []}


def test_discover_missing_root_path(tmp_path: Path) -> None:
    raw = req("discover") + "\n"
    response = responses(_run(raw))[0]
    assert response["error"]["code"] == INVALID_PARAMS


def test_discover_non_object_params(tmp_path: Path) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "discover", "params": []}
    raw = json.dumps(body) + "\n"
    response = responses(_run(raw))[0]
    assert response["error"]["code"] == INVALID_PARAMS


def test_discover_nonexistent_root(tmp_path: Path) -> None:
    raw = req("discover", root_path=str(tmp_path / "nope")) + "\n"
    response = responses(_run(raw))[0]
    assert response["error"]["code"] == INVALID_PARAMS


def test_discover_non_string_root(tmp_path: Path) -> None:
    raw = req("discover", root_path=123) + "\n"
    response = responses(_run(raw))[0]
    assert response["error"]["code"] == INVALID_PARAMS


def test_discover_non_array_patterns(tmp_path: Path) -> None:
    raw = req("discover", root_path=str(tmp_path), patterns="src") + "\n"
    response = responses(_run(raw))[0]
    assert response["error"]["code"] == INVALID_PARAMS


def test_initialize_reports_discover_true() -> None:
    raw = req("initialize", root_path="/abs") + "\n"
    response = responses(_run(raw))[0]
    assert response["result"] == initialize_result()
    capabilities = response["result"]["capabilities"]
    assert capabilities["discover"] is True
    assert capabilities["test_mapping"] is False
    assert capabilities["classify_signals"] is False
    assert capabilities["streaming"] is False
