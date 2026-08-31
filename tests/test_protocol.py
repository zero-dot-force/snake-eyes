"""Tests for the JSON-RPC 2.0 protocol types and serialization."""

from __future__ import annotations

import json
import sys

from snake_eyes.protocol import (
    ANALYZER_NAME,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    LANGUAGE,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PROTOCOL_VERSION,
    JsonRpcError,
    JsonRpcErrorBody,
    JsonRpcRequest,
    JsonRpcSuccess,
    initialize_result,
    shutdown_result,
    to_dict,
    to_json,
)


def test_error_code_constants_are_exact() -> None:
    assert PARSE_ERROR == -32700
    assert INVALID_REQUEST == -32600
    assert METHOD_NOT_FOUND == -32601
    assert INVALID_PARAMS == -32602
    assert INTERNAL_ERROR == -32603


def test_request_round_trip_exact_keys() -> None:
    request = JsonRpcRequest("2.0", 1, "initialize", {"root_path": "/abs"})
    serialized = json.loads(to_json(request))
    assert serialized == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"root_path": "/abs"},
    }


def test_falsy_id_round_trips_unchanged() -> None:
    zero = to_dict(JsonRpcSuccess(0, {}))
    string_id = to_dict(JsonRpcSuccess("abc", {}))
    assert zero["id"] == 0
    assert not isinstance(zero["id"], bool)
    assert string_id["id"] == "abc"


def test_success_serializes_result() -> None:
    success = JsonRpcSuccess(7, {"ok": True})
    serialized = json.loads(to_json(success))
    assert serialized == {"jsonrpc": "2.0", "id": 7, "result": {"ok": True}}


def test_error_serializes_nested_body_with_data() -> None:
    error = JsonRpcError(3, JsonRpcErrorBody(INTERNAL_ERROR, "boom", {"detail": 1}))
    serialized = json.loads(to_json(error))
    assert serialized == {
        "jsonrpc": "2.0",
        "id": 3,
        "error": {"code": INTERNAL_ERROR, "message": "boom", "data": {"detail": 1}},
    }


def test_error_none_data_is_omitted() -> None:
    error = JsonRpcError(None, JsonRpcErrorBody(PARSE_ERROR, "Parse error"))
    serialized = json.loads(to_json(error))
    assert "data" not in serialized["error"]
    assert "data" not in to_json(error)


def test_initialize_result_schema() -> None:
    result = initialize_result()
    assert result["analyzer_name"] == ANALYZER_NAME == "snake-eyes"
    assert result["language"] == LANGUAGE == "python"
    assert result["protocol_version"] == PROTOCOL_VERSION == "1.1.0"

    major, minor, micro = sys.version_info[:3]
    assert result["language_version"] == f"{major}.{minor}.{micro}"

    assert result["capabilities"] == {
        "discover": True,
        "test_mapping": False,
        "classify_signals": True,
        "streaming": False,
    }


def test_shutdown_result_is_empty_object() -> None:
    assert shutdown_result() == {}


def test_to_dict_handles_list_values() -> None:
    request = JsonRpcRequest("2.0", 1, "initialize", {"items": [1, 2]})
    assert to_dict(request)["params"]["items"] == [1, 2]
