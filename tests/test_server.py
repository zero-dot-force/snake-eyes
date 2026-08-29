"""Tests for the JSON-RPC stdio server loop."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping

import pytest
from conftest import req, responses

from snake_eyes.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    initialize_result,
)
from snake_eyes.server import MAX_LINE_CHARS, Handler, Server


def _run(raw: str, dispatch: Mapping[str, Handler] | None = None) -> tuple[str, str]:
    stdin = io.StringIO(raw)
    stdout = io.StringIO()
    stderr = io.StringIO()
    server = Server(stdin, stdout, stderr, dispatch=dispatch)
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    return stdout.getvalue(), stderr.getvalue()


class _FlushSpy(io.StringIO):
    """A StringIO that records flush calls so transport flushing is pinned."""

    def __init__(self) -> None:
        super().__init__()
        self.flushes = 0

    def flush(self) -> None:
        self.flushes += 1
        super().flush()


class _UndecodableStdin(io.StringIO):
    """A stdin stub whose first readline raises UnicodeDecodeError."""

    def __init__(self) -> None:
        super().__init__("")
        self._raised = False

    def readline(self, size: int = -1) -> str:
        if not self._raised:
            self._raised = True
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return super().readline(size)


def test_initialize_roundtrip() -> None:
    stdout, _ = _run(req("initialize", root_path="/abs") + "\n")
    assert responses(stdout) == [
        {"jsonrpc": "2.0", "id": 1, "result": initialize_result()}
    ]


def test_initialize_accepts_optional_config() -> None:
    stdout, _ = _run(req("initialize", root_path="/abs", config={}) + "\n")
    response = responses(stdout)[0]
    assert response["result"] == initialize_result()


def test_unknown_method() -> None:
    stdout, _ = _run(req("nope") + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == METHOD_NOT_FOUND
    assert response["error"]["message"] == "Method not found: nope"


def test_method_not_found_truncates_long_method_name() -> None:
    stdout, _ = _run(req("x" * 100) + "\n")
    message = responses(stdout)[0]["error"]["message"]
    assert message == "Method not found: " + "x" * 61 + "..."


def test_malformed_json_then_still_alive() -> None:
    raw = "{not json\n" + req("initialize", root_path="/x") + "\n"
    stdout, _ = _run(raw)
    result = responses(stdout)
    assert len(result) == 2
    assert result[0]["error"]["code"] == PARSE_ERROR
    assert result[0]["id"] is None
    assert result[1]["result"]["analyzer_name"] == "snake-eyes"


def test_deeply_nested_json_yields_parse_error() -> None:
    raw = "[" * 100_000 + "\n" + req("initialize", root_path="/x", id=2) + "\n"
    stdout, _ = _run(raw)
    result = responses(stdout)
    assert len(result) == 2
    assert result[0]["error"]["code"] == PARSE_ERROR
    assert result[0]["id"] is None
    assert result[1]["result"]["analyzer_name"] == "snake-eyes"


def test_oversize_line_rejected_then_still_alive() -> None:
    oversize = "[" * (MAX_LINE_CHARS + 1)
    raw = oversize + "\n" + req("initialize", root_path="/x", id=2) + "\n"
    stdout, _ = _run(raw)
    result = responses(stdout)
    assert len(result) == 2
    assert result[0]["error"]["code"] == INVALID_REQUEST
    assert result[0]["id"] is None
    assert result[1]["result"]["analyzer_name"] == "snake-eyes"


def test_undecodable_input_yields_parse_error() -> None:
    stdout = io.StringIO()
    server = Server(_UndecodableStdin(), stdout, io.StringIO())
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    response = responses(stdout.getvalue())[0]
    assert response["error"]["code"] == PARSE_ERROR
    assert response["id"] is None


def test_every_response_is_flushed() -> None:
    stdin = io.StringIO(req("initialize", root_path="/x") + "\n" + req("nope") + "\n")
    stdout = _FlushSpy()
    server = Server(stdin, stdout, io.StringIO())
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    assert stdout.flushes == 2  # one flush per response line


def test_missing_method_field() -> None:
    stdout, _ = _run(json.dumps({"jsonrpc": "2.0", "id": 1}) + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == INVALID_REQUEST
    assert response["id"] == 1


def test_missing_jsonrpc_field() -> None:
    stdout, _ = _run(json.dumps({"id": 1, "method": "initialize"}) + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == INVALID_REQUEST
    assert response["id"] == 1


def test_non_object_request() -> None:
    stdout, _ = _run("[1, 2, 3]\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == INVALID_REQUEST
    assert response["id"] is None


def test_wrong_jsonrpc_version() -> None:
    stdout, _ = _run(json.dumps({"jsonrpc": "1.0", "id": 1, "method": "x"}) + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == INVALID_REQUEST
    assert response["id"] == 1


@pytest.mark.parametrize("blank", ["\n", "   \n", "\t\n", "\r\n"])
def test_blank_lines_ignored(blank: str) -> None:
    raw = req("initialize", root_path="/x") + "\n" + blank
    stdout, _ = _run(raw)
    assert len(responses(stdout)) == 1


def test_crlf_line_endings() -> None:
    raw = req("initialize", root_path="/x") + "\r\n"
    stdout, _ = _run(raw)
    result = responses(stdout)
    assert len(result) == 1
    assert result[0]["result"]["analyzer_name"] == "snake-eyes"


def test_requests_handled_in_order() -> None:
    raw = req("initialize", root_path="/x", id=1) + "\n" + req("nope", id=2) + "\n"
    stdout, _ = _run(raw)
    assert [r["id"] for r in responses(stdout)] == [1, 2]


def test_repeated_initialize() -> None:
    init = req("initialize", root_path="/x")
    raw = init + "\n" + init + "\n"
    stdout, _ = _run(raw)
    result = responses(stdout)
    assert len(result) == 2
    assert all(r["result"] == initialize_result() for r in result)


def test_invalid_params_missing_root_path() -> None:
    raw = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    stdout, _ = _run(raw + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == INVALID_PARAMS
    assert response["error"]["message"] == "Invalid params: root_path must be a string"
    assert response["id"] == 1


def test_invalid_params_non_object() -> None:
    raw = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": []})
    stdout, _ = _run(raw + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == INVALID_PARAMS
    assert response["error"]["message"] == "Invalid params: params must be an object"
    assert response["id"] == 1


def test_invalid_params_absent() -> None:
    raw = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    stdout, _ = _run(raw + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == INVALID_PARAMS
    assert response["error"]["message"] == "Invalid params: params must be an object"
    assert response["id"] == 1


@pytest.mark.parametrize("root_path", [42, True, 3.5, ["x"]])
def test_invalid_params_root_path_wrong_type(root_path: object) -> None:
    stdout, _ = _run(req("initialize", root_path=root_path) + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == INVALID_PARAMS
    assert response["error"]["message"] == "Invalid params: root_path must be a string"


@pytest.mark.parametrize(
    "method",
    [
        # analyze/complexity/coverage are now implemented (return -32602 without params)
        "test_mapping",
        "classify_signals",
        "analyze/stream",
    ],
)
def test_reserved_methods_not_implemented(method: str) -> None:
    stdout, _ = _run(req(method) + "\n")
    response = responses(stdout)[0]
    assert response["error"]["code"] == METHOD_NOT_FOUND


def test_shutdown_returns_empty_object() -> None:
    raw = json.dumps({"jsonrpc": "2.0", "id": 9, "method": "shutdown"})
    stdout, _ = _run(raw + "\n")
    assert responses(stdout) == [{"jsonrpc": "2.0", "id": 9, "result": {}}]


def test_shutdown_accepts_null_params() -> None:
    raw = json.dumps({"jsonrpc": "2.0", "id": 9, "method": "shutdown", "params": None})
    stdout, _ = _run(raw + "\n")
    assert responses(stdout)[0] == {"jsonrpc": "2.0", "id": 9, "result": {}}


def test_shutdown_terminates_the_loop() -> None:
    raw = req("shutdown", id=9) + "\n" + req("initialize", root_path="/x", id=10) + "\n"
    stdout, _ = _run(raw)
    assert responses(stdout) == [{"jsonrpc": "2.0", "id": 9, "result": {}}]


def test_eof_exits_cleanly() -> None:
    stdout, _ = _run("")
    assert stdout == ""


class _BrokenPipeWriter:
    def write(self, s: str) -> int:
        raise BrokenPipeError()

    def flush(self) -> None:
        pass


class _EIOWriter:
    def write(self, s: str) -> int:
        raise OSError(5, "Input/output error")

    def flush(self) -> None:
        pass


def test_broken_pipe_is_clean_teardown() -> None:
    stdin = io.StringIO(req("initialize", root_path="/x") + "\n")
    stderr = io.StringIO()
    server = Server(stdin, _BrokenPipeWriter(), stderr)
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    assert "Traceback" not in stderr.getvalue()


def test_write_failure_is_clean_teardown() -> None:
    stdin = io.StringIO(req("initialize", root_path="/x") + "\n")
    stderr = io.StringIO()
    server = Server(stdin, _EIOWriter(), stderr)
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    assert "Traceback" not in stderr.getvalue()


def test_internal_error_via_injected_handler() -> None:
    def boom(params: object) -> dict[str, object]:
        raise RuntimeError("boom")

    stdout, stderr = _run(req("boom") + "\n", dispatch={"boom": boom})
    response = responses(stdout)[0]
    assert response["error"]["code"] == INTERNAL_ERROR
    assert response["error"]["message"] == "Internal error"
    assert "Traceback" in stderr


@pytest.mark.parametrize("request_id", [0, "abc"])
def test_falsy_and_string_id_round_trip(request_id: object) -> None:
    stdout, _ = _run(req("initialize", root_path="/x", id=request_id) + "\n")
    response = responses(stdout)[0]
    assert response["id"] == request_id


@pytest.mark.parametrize("request_id", [[1], 1.5, None])
def test_non_scalar_id_yields_null(request_id: object) -> None:
    raw = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {"root_path": "/x"},
        }
    )
    stdout, _ = _run(raw + "\n")
    assert responses(stdout)[0]["id"] is None


@pytest.mark.parametrize("request_id", [True, False])
def test_boolean_id_yields_null(request_id: bool) -> None:
    raw = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {"root_path": "/x"},
        }
    )
    stdout, _ = _run(raw + "\n")
    assert responses(stdout)[0]["id"] is None
