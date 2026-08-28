"""Line-delimited JSON-RPC 2.0 stdio server for snake-eyes."""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections.abc import Callable, Mapping
from typing import Any, TextIO

from .discovery import discover
from .protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcError,
    JsonRpcErrorBody,
    JsonRpcSuccess,
    initialize_result,
    shutdown_result,
    to_json,
)

SHUTDOWN_METHOD = "shutdown"

# Bound on a single request line. Oversize lines are rejected before parsing,
# bounding parse-time allocation (the dominant memory blow-up vector).
MAX_LINE_CHARS = 16 * 1024 * 1024  # 16 MiB

# Bound on the client-controlled method name echoed in -32601 responses.
MAX_METHOD_ECHO = 64

Handler = Callable[[dict[str, Any] | None], dict[str, Any]]


class RpcError(Exception):
    """A deliberate JSON-RPC error a handler reports to the client."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _initialize(params: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise RpcError(INVALID_PARAMS, "Invalid params: params must be an object")
    root_path = params.get("root_path")
    if not isinstance(root_path, str):
        raise RpcError(INVALID_PARAMS, "Invalid params: root_path must be a string")
    return initialize_result()


def _shutdown(params: dict[str, Any] | None) -> dict[str, Any]:
    return shutdown_result()


def _discover(params: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise RpcError(INVALID_PARAMS, "Invalid params: params must be an object")
    root_path = params.get("root_path")
    if not isinstance(root_path, str):
        raise RpcError(INVALID_PARAMS, "Invalid params: root_path must be a string")
    patterns_raw = params.get("patterns")
    if patterns_raw is not None and (
        not isinstance(patterns_raw, list)
        or not all(isinstance(pattern, str) for pattern in patterns_raw)
    ):
        raise RpcError(
            INVALID_PARAMS, "Invalid params: patterns must be an array of strings"
        )
    patterns: list[str] | None = patterns_raw
    try:
        result = discover(root_path, patterns)
    except FileNotFoundError as err:
        raise RpcError(INVALID_PARAMS, str(err)) from err
    return {
        "source_files": list(result.source_files),
        "test_files": list(result.test_files),
    }


DEFAULT_DISPATCH: Mapping[str, Handler] = {
    "initialize": _initialize,
    SHUTDOWN_METHOD: _shutdown,
    "discover": _discover,
}


class Server:
    """A sequential JSON-RPC 2.0 server reading lines from stdin and writing
    responses to stdout.

    The constructor takes the three stdio streams (tests inject
    ``io.StringIO``) and an optional ``dispatch`` table mapping method names
    to handler callables. A supplied ``dispatch`` **replaces** the built-in
    ``initialize``/``shutdown`` table (it is not merged), letting tests
    register handlers -- including raising ones -- through the normal
    stdin/stdout loop.
    """

    def __init__(
        self,
        stdin: TextIO,
        stdout: TextIO,
        stderr: TextIO,
        dispatch: Mapping[str, Handler] | None = None,
    ) -> None:
        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr
        self._dispatch = DEFAULT_DISPATCH if dispatch is None else dispatch

    def run(self) -> None:
        """Read and dispatch request lines until EOF or ``shutdown``.

        Input that fails to decode as text is answered with a parse error and
        the loop continues, per the stay-alive posture for malformed input.
        Raises ``SystemExit(0)`` on EOF, after ``shutdown``, or when the
        output pipe breaks.
        """
        while True:
            try:
                line = self._stdin.readline()
            except UnicodeDecodeError:
                self._respond_error(None, PARSE_ERROR, "Parse error")
                continue
            if line == "":
                break
            self._handle_line(line)
        raise SystemExit(0)

    def _handle_line(self, line: str) -> None:
        line = line.rstrip("\r\n")
        if not line.strip():
            return
        if len(line) > MAX_LINE_CHARS:
            self._respond_error(None, INVALID_REQUEST, "Invalid Request")
            return

        try:
            data = json.loads(line)
        except (json.JSONDecodeError, RecursionError):
            self._respond_error(None, PARSE_ERROR, "Parse error")
            return

        if not isinstance(data, dict):
            self._respond_error(None, INVALID_REQUEST, "Invalid Request")
            return

        request_id = _extract_id(data)
        jsonrpc = data.get("jsonrpc")
        method = data.get("method")

        if jsonrpc != "2.0" or not isinstance(method, str):
            self._respond_error(request_id, INVALID_REQUEST, "Invalid Request")
            return

        params = data.get("params")
        handler = self._dispatch.get(method)
        if handler is None:
            self._respond_error(
                request_id,
                METHOD_NOT_FOUND,
                f"Method not found: {_truncate(method, MAX_METHOD_ECHO)}",
            )
            return

        try:
            result = handler(params)
        except RpcError as err:
            self._respond_error(request_id, err.code, err.message)
        except Exception as err:
            traceback.print_exc(file=self._stderr)
            self._respond_error(request_id, INTERNAL_ERROR, str(err))
        else:
            self._respond(JsonRpcSuccess(request_id, result))

        if method == SHUTDOWN_METHOD:
            raise SystemExit(0)

    def _respond_error(
        self, request_id: int | str | None, code: int, message: str
    ) -> None:
        """Send a JSON-RPC error response with the given code and message."""
        self._respond(JsonRpcError(request_id, JsonRpcErrorBody(code, message)))

    def _respond(self, response: JsonRpcSuccess | JsonRpcError) -> None:
        try:
            self._stdout.write(to_json(response) + "\n")
            self._stdout.flush()
        except OSError:
            # A failed write (e.g. EPIPE when Gaze closes the pipe) is clean
            # teardown. When the broken stream is the real process stdout,
            # redirect it to devnull first so interpreter finalization does
            # not re-flush the broken pipe (which can exit 120 on 3.12+).
            # The real-stdout branch cannot be exercised in-process without
            # redirecting the test runner's own stdout.
            if self._stdout is sys.stdout:  # pragma: no cover
                _devnull_stdout()
            raise SystemExit(0)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


# Only reachable with a real broken pipe; cannot be exercised in-process
# without redirecting the test runner's own stdout.
def _devnull_stdout() -> None:  # pragma: no cover
    """Redirect process stdout to devnull (best effort)."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        os.close(devnull)
    except OSError:
        pass


def _extract_id(data: dict[Any, Any]) -> int | str | None:
    request_id = data.get("id")
    if isinstance(request_id, (int, str)) and not isinstance(request_id, bool):
        return request_id
    return None
