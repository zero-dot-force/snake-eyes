"""Tests for the JSON-RPC stdio server loop."""

from __future__ import annotations

import io
import json

import pytest

from snake_eyes.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PROTOCOL_VERSION,
)
from snake_eyes.server import Server


def _run(raw: str, dispatch=None) -> tuple[str, str]:
    stdin = io.StringIO(raw)
    stdout = io.StringIO()
    stderr = io.StringIO()
    server = Server(stdin, stdout, stderr, dispatch=dispatch)
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    return stdout.getvalue(), stderr.getvalue()


def _responses(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line]


def _req(method: str, id=1, **params: object) -> str:
    obj: dict[str, object] = {"jsonrpc": "2.0", "id": id, "method": method}
    if params:
        obj["params"] = params
    return json.dumps(obj)


def test_initialize_roundtrip() -> None:
    stdout, _ = _run(_req("initialize", root_path="/abs") + "\n")
    responses = _responses(stdout)
    assert len(responses) == 1
    response = responses[0]
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["analyzer_name"] == "snake-eyes"
    assert response["result"]["language"] == "python"
    assert response["result"]["protocol_version"] == PROTOCOL_VERSION == "1.1.0"
    assert response["result"]["capabilities"] == {
        "discover": False,
        "test_mapping": False,
        "classify_signals": False,
        "streaming": False,
    }


def test_unknown_method() -> None:
    stdout, _ = _run(_req("nope") + "\n")
    response = _responses(stdout)[0]
    assert response["error"]["code"] == METHOD_NOT_FOUND
    assert response["error"]["message"] == "Method not found: nope"


def test_malformed_json_then_still_alive() -> None:
    raw = "{not json\n" + _req("initialize", root_path="/x") + "\n"
    stdout, _ = _run(raw)
    responses = _responses(stdout)
    assert len(responses) == 2
    assert responses[0]["error"]["code"] == PARSE_ERROR
    assert responses[0]["id"] is None
    assert responses[1]["result"]["analyzer_name"] == "snake-eyes"


def test_missing_method_field() -> None:
    stdout, _ = _run(json.dumps({"jsonrpc": "2.0", "id": 1}) + "\n")
    response = _responses(stdout)[0]
    assert response["error"]["code"] == INVALID_REQUEST
    assert response["id"] == 1


def test_missing_jsonrpc_field() -> None:
    stdout, _ = _run(json.dumps({"id": 1, "method": "initialize"}) + "\n")
    response = _responses(stdout)[0]
    assert response["error"]["code"] == INVALID_REQUEST
    assert response["id"] == 1


def test_non_object_request() -> None:
    stdout, _ = _run("[1, 2, 3]\n")
    response = _responses(stdout)[0]
    assert response["error"]["code"] == INVALID_REQUEST
    assert response["id"] is None


def test_wrong_jsonrpc_version() -> None:
    stdout, _ = _run(json.dumps({"jsonrpc": "1.0", "id": 1, "method": "x"}) + "\n")
    response = _responses(stdout)[0]
    assert response["error"]["code"] == INVALID_REQUEST
    assert response["id"] == 1


def test_empty_line_ignored() -> None:
    raw = (
        _req("initialize", root_path="/x")
        + "\n\n"
        + _req("initialize", root_path="/x")
        + "\n"
    )
    stdout, _ = _run(raw)
    assert len(_responses(stdout)) == 2


def test_crlf_line_endings() -> None:
    raw = _req("initialize", root_path="/x") + "\r\n"
    stdout, _ = _run(raw)
    responses = _responses(stdout)
    assert len(responses) == 1
    assert responses[0]["result"]["analyzer_name"] == "snake-eyes"


def test_requests_handled_in_order() -> None:
    raw = _req("initialize", root_path="/x", id=1) + "\n" + _req("nope", id=2) + "\n"
    stdout, _ = _run(raw)
    responses = _responses(stdout)
    assert [r["id"] for r in responses] == [1, 2]


def test_repeated_initialize() -> None:
    raw = (
        _req("initialize", root_path="/x")
        + "\n"
        + _req("initialize", root_path="/x")
        + "\n"
    )
    stdout, _ = _run(raw)
    responses = _responses(stdout)
    assert len(responses) == 2
    assert all("result" in r for r in responses)


def test_invalid_params_missing_root_path() -> None:
    stdout, _ = _run(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + "\n"
    )
    response = _responses(stdout)[0]
    assert response["error"]["code"] == INVALID_PARAMS


def test_invalid_params_non_object() -> None:
    stdout, _ = _run(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": []})
        + "\n"
    )
    response = _responses(stdout)[0]
    assert response["error"]["code"] == INVALID_PARAMS


def test_invalid_params_absent() -> None:
    stdout, _ = _run(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n"
    )
    response = _responses(stdout)[0]
    assert response["error"]["code"] == INVALID_PARAMS


@pytest.mark.parametrize(
    "method",
    [
        "analyze",
        "complexity",
        "coverage",
        "discover",
        "test_mapping",
        "classify_signals",
        "analyze/stream",
    ],
)
def test_reserved_methods_not_implemented(method: str) -> None:
    stdout, _ = _run(_req(method) + "\n")
    response = _responses(stdout)[0]
    assert response["error"]["code"] == METHOD_NOT_FOUND


def test_shutdown_returns_empty_object() -> None:
    stdout, _ = _run(
        json.dumps({"jsonrpc": "2.0", "id": 9, "method": "shutdown"}) + "\n"
    )
    responses = _responses(stdout)
    assert len(responses) == 1
    assert responses[0] == {"jsonrpc": "2.0", "id": 9, "result": {}}


def test_eof_exits_cleanly() -> None:
    stdout, _ = _run("")
    assert stdout == ""


class _BrokenPipeWriter:
    def write(self, s: str) -> int:
        raise BrokenPipeError()

    def flush(self) -> None:
        pass


def test_broken_pipe_is_clean_teardown() -> None:
    stdin = io.StringIO(_req("initialize", root_path="/x") + "\n")
    stderr = io.StringIO()
    server = Server(stdin, _BrokenPipeWriter(), stderr)
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0


def test_internal_error_via_injected_handler() -> None:
    def boom(params):
        raise RuntimeError("boom")

    stdout, stderr = _run(_req("boom") + "\n", dispatch={"boom": boom})
    response = _responses(stdout)[0]
    assert response["error"]["code"] == INTERNAL_ERROR
    assert response["error"]["message"] == "boom"
    assert "Traceback" in stderr


@pytest.mark.parametrize("request_id", [0, "abc"])
def test_falsy_and_string_id_round_trip(request_id: object) -> None:
    stdout, _ = _run(_req("initialize", root_path="/x", id=request_id) + "\n")
    response = _responses(stdout)[0]
    assert response["id"] == request_id


def test_non_scalar_id_yields_null() -> None:
    raw = (
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": [1],
                "method": "initialize",
                "params": {"root_path": "/x"},
            }
        )
        + "\n"
    )
    stdout, _ = _run(raw)
    response = _responses(stdout)[0]
    assert response["id"] is None
