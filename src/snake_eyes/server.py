"""Line-delimited JSON-RPC 2.0 stdio server for snake-eyes."""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable, Mapping
from typing import Any, TextIO

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

Handler = Callable[[dict[str, Any] | None], dict[str, Any]]


class RpcError(Exception):
    """A deliberate JSON-RPC error a handler reports to the client."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _initialize(params: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise RpcError(INVALID_PARAMS, "Invalid params")
    root_path = params.get("root_path")
    if not isinstance(root_path, str):
        raise RpcError(INVALID_PARAMS, "Invalid params")
    return initialize_result()


def _shutdown(params: dict[str, Any] | None) -> dict[str, Any]:
    return shutdown_result()


DEFAULT_DISPATCH: Mapping[str, Handler] = {
    "initialize": _initialize,
    SHUTDOWN_METHOD: _shutdown,
}


class Server:
    """A sequential JSON-RPC 2.0 server reading lines from stdin and writing
    responses to stdout."""

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
        """Read and dispatch request lines until EOF or ``shutdown``."""
        for line in self._stdin:
            self._handle_line(line)
        raise SystemExit(0)

    def _handle_line(self, line: str) -> None:
        line = line.rstrip("\r\n")
        if not line:
            return

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            self._respond(
                JsonRpcError(None, JsonRpcErrorBody(PARSE_ERROR, "Parse error"))
            )
            return

        if not isinstance(data, dict):
            self._respond(
                JsonRpcError(None, JsonRpcErrorBody(INVALID_REQUEST, "Invalid Request"))
            )
            return

        request_id = _extract_id(data)
        jsonrpc = data.get("jsonrpc")
        method = data.get("method")

        if jsonrpc != "2.0" or not isinstance(method, str):
            self._respond(
                JsonRpcError(
                    request_id, JsonRpcErrorBody(INVALID_REQUEST, "Invalid Request")
                )
            )
            return

        params = data.get("params")
        handler = self._dispatch.get(method)
        if handler is None:
            self._respond(
                JsonRpcError(
                    request_id,
                    JsonRpcErrorBody(METHOD_NOT_FOUND, f"Method not found: {method}"),
                )
            )
            return

        try:
            result = handler(params)
        except RpcError as err:
            self._respond(
                JsonRpcError(request_id, JsonRpcErrorBody(err.code, err.message))
            )
        except Exception as err:
            traceback.print_exc(file=self._stderr)
            self._respond(
                JsonRpcError(request_id, JsonRpcErrorBody(INTERNAL_ERROR, str(err)))
            )
        else:
            self._respond(JsonRpcSuccess(request_id, result))

        if method == SHUTDOWN_METHOD:
            raise SystemExit(0)

    def _respond(self, response: JsonRpcSuccess | JsonRpcError) -> None:
        try:
            self._stdout.write(to_json(response) + "\n")
            self._stdout.flush()
        except BrokenPipeError:
            raise SystemExit(0)


def _extract_id(data: dict[Any, Any]) -> int | str | None:
    request_id = data.get("id")
    if isinstance(request_id, (int, str)):
        return request_id
    return None
