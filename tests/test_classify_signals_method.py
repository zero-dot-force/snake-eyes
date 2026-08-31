"""JSON-RPC end-to-end tests for the classify_signals method."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from conftest import req, responses

from snake_eyes.protocol import INVALID_PARAMS
from snake_eyes.server import Server


def _run(raw: str) -> str:
    stdout = io.StringIO()
    server = Server(io.StringIO(raw), stdout, io.StringIO())
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    return stdout.getvalue()


def _module(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        "def get_v(a):\n"
        '    """Returns a value."""\n'
        "    return a\n\n"
        "def caller():\n"
        "    return get_v(1)\n"
    )


def test_initialize_advertises_classify_signals(tmp_path: Path) -> None:
    resp = responses(_run(req("initialize", root_path=str(tmp_path)) + "\n"))[0]
    caps = resp["result"]["capabilities"]
    assert caps["classify_signals"] is True
    assert caps["test_mapping"] is False
    assert caps["streaming"] is False


def test_classify_signals_returns_signal_array(tmp_path: Path) -> None:
    _module(tmp_path)
    resp = responses(_run(req("classify_signals", root_path=str(tmp_path)) + "\n"))[0]
    signals = resp["result"]["signals"]
    assert isinstance(signals, list)
    for signal in signals:
        assert signal["function"]
        assert signal["package"] is not None
        assert isinstance(signal["reasoning"], str)
        assert signal["reasoning"]


def test_missing_root_path_is_invalid_params(tmp_path: Path) -> None:
    resp = responses(_run(req("classify_signals") + "\n"))[0]
    assert resp["error"]["code"] == INVALID_PARAMS


def test_non_string_root_path_is_invalid_params() -> None:
    resp = responses(_run(req("classify_signals", root_path=123) + "\n"))[0]
    assert resp["error"]["code"] == INVALID_PARAMS


def test_non_array_patterns_is_invalid_params(tmp_path: Path) -> None:
    raw = req("classify_signals", root_path=str(tmp_path), patterns="oops") + "\n"
    resp = responses(_run(raw))[0]
    assert resp["error"]["code"] == INVALID_PARAMS


def test_non_string_pattern_element_is_invalid_params(tmp_path: Path) -> None:
    raw = req("classify_signals", root_path=str(tmp_path), patterns=[1]) + "\n"
    resp = responses(_run(raw))[0]
    assert resp["error"]["code"] == INVALID_PARAMS


def test_output_is_deterministic(tmp_path: Path) -> None:
    _module(tmp_path)
    raw = req("classify_signals", root_path=str(tmp_path)) + "\n"
    assert _run(raw) == _run(raw)
