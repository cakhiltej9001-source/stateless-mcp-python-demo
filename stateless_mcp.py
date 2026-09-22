"""Dependency-free teaching demo of the stateless MCP wire model."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "stateless-task-1-demo", "version": "1.0.0"}


class ProtocolError(Exception):
    def __init__(self, code: int, message: str, data: Any = None, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.data, self.status = code, message, data, status


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class RequestStateCodec:
    """Integrity-protect opaque state that makes a retry self-contained."""

    key: bytes
    ttl_seconds: int = 300

    def mint(self, payload: Mapping[str, Any]) -> str:
        body = {**payload, "exp": int(time.time()) + self.ttl_seconds}
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self.key, raw, hashlib.sha256).digest()
        return f"{_b64encode(raw)}.{_b64encode(signature)}"

    def verify(self, token: str) -> dict[str, Any]:
        try:
            encoded_body, encoded_signature = token.split(".", 1)
            raw = _b64decode(encoded_body)
            signature = _b64decode(encoded_signature)
            expected = hmac.new(self.key, raw, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("bad signature")
            payload = json.loads(raw)
            if payload["exp"] < int(time.time()):
                raise ValueError("expired")
            return payload
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ProtocolError(-32602, "Invalid or expired requestState") from exc


def _server_meta() -> dict[str, Any]:
    return {"io.modelcontextprotocol/serverInfo": SERVER_INFO}


def complete(result: Mapping[str, Any]) -> dict[str, Any]:
    return {"resultType": "complete", **result, "_meta": _server_meta()}


def input_required(input_requests: Mapping[str, Any], state: str) -> dict[str, Any]:
    return {
        "resultType": "input_required",
        "inputRequests": dict(input_requests),
        "requestState": state,
        "_meta": _server_meta(),
    }


def _validate_envelope(params: Mapping[str, Any], headers: Mapping[str, str]) -> dict[str, Any]:
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise ProtocolError(-32602, "params._meta is required")
    body_version = meta.get("io.modelcontextprotocol/protocolVersion")
    header_version = headers.get("mcp-protocol-version")
    if body_version != header_version:
        raise ProtocolError(-32020, "MCP-Protocol-Version header/body mismatch")
    if body_version != PROTOCOL_VERSION:
        raise ProtocolError(-32022, "Unsupported protocol version", {
            "supported": [PROTOCOL_VERSION], "requested": body_version
        })
    capabilities = meta.get("io.modelcontextprotocol/clientCapabilities")
    if not isinstance(capabilities, dict):
        raise ProtocolError(-32602, "clientCapabilities must be supplied per request")
    return capabilities


def _supports_form_elicitation(capabilities: Mapping[str, Any]) -> bool:
    elicitation = capabilities.get("elicitation")
    return isinstance(elicitation, dict) and isinstance(elicitation.get("form"), dict)


def _confirmation_response(params: Mapping[str, Any]) -> dict[str, Any] | None:
    responses = params.get("inputResponses")
    if not isinstance(responses, dict):
        return None
    response = responses.get("confirm")
    if not isinstance(response, dict) or response.get("action") != "accept":
        return None
    content = response.get("content")
    return content if isinstance(content, dict) else None


def handle_rpc(request: Mapping[str, Any], headers: Mapping[str, str],
               codec: RequestStateCodec) -> tuple[int, dict[str, Any]]:
    """Handle one independent JSON-RPC request and return HTTP status/body."""
    request_id = request.get("id")
    try:
        if request.get("jsonrpc") != "2.0" or request_id is None:
            raise ProtocolError(-32600, "Invalid JSON-RPC request")
        method, params = request.get("method"), request.get("params", {})
        if not isinstance(params, dict):
            raise ProtocolError(-32602, "params must be an object")
        capabilities = _validate_envelope(params, headers)
        if headers.get("mcp-method") != method:
            raise ProtocolError(-32020, "Mcp-Method header/body mismatch")

        if method == "server/discover":
            result = complete({
                "supportedVersions": [PROTOCOL_VERSION],
                "capabilities": {"tools": {}},
                "instructions": "Call confirm_operation to observe stateless elicitation.",
            })
        elif method == "tools/list":
            result = complete({
                "tools": [{
                    "name": "confirm_operation",
                    "description": "Completes an operation only after user confirmation.",
                    "inputSchema": {"type": "object", "properties": {
                        "operation": {"type": "string"}}, "required": ["operation"]},
                }],
                "ttlMs": 0, "cacheScope": "private",
            })
        elif method == "tools/call":
            result = _call_tool(params, capabilities, headers, codec)
        else:
            raise ProtocolError(-32601, "Method not found", status=404)
        return 200, {"jsonrpc": "2.0", "id": request_id, "result": result}
    except ProtocolError as exc:
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.data is not None:
            error["data"] = exc.data
        return exc.status, {"jsonrpc": "2.0", "id": request_id, "error": error}


def _call_tool(params: Mapping[str, Any], capabilities: Mapping[str, Any],
               headers: Mapping[str, str], codec: RequestStateCodec) -> dict[str, Any]:
    if params.get("name") != "confirm_operation":
        raise ProtocolError(-32602, "Unknown tool")
    if headers.get("mcp-name") != params.get("name"):
        raise ProtocolError(-32020, "Mcp-Name header/body mismatch")
    arguments = params.get("arguments")
    if not isinstance(arguments, dict) or not isinstance(arguments.get("operation"), str):
        raise ProtocolError(-32602, "arguments.operation must be a string")
    operation = arguments["operation"]
    answer, state_token = _confirmation_response(params), params.get("requestState")

    if answer is None:
        if not _supports_form_elicitation(capabilities):
            raise ProtocolError(-32021, "Client does not declare form elicitation support",
                                {"requiredCapabilities": {"elicitation": {"form": {}}}})
        state = codec.mint({"tool": "confirm_operation", "operation": operation})
        return input_required({"confirm": {
            "method": "elicitation/create",
            "params": {"mode": "form", "message": f"Allow operation: {operation}?",
                       "requestedSchema": {"type": "object", "properties": {
                           "confirmed": {"type": "boolean"}}, "required": ["confirmed"]}},
        }}, state)

    if not isinstance(state_token, str):
        raise ProtocolError(-32602, "requestState must be echoed with inputResponses")
    state = codec.verify(state_token)
    if state.get("tool") != "confirm_operation" or state.get("operation") != operation:
        raise ProtocolError(-32602, "requestState is not bound to this tool call")
    if answer.get("confirmed") is not True:
        return complete({"content": [{"type": "text", "text":
                         "Operation cancelled by the user."}], "isError": True})
    return complete({"content": [{"type": "text", "text": f"Completed: {operation}"}],
                     "isError": False})


def codec_from_environment() -> RequestStateCodec:
    # Inject a stable secret in production; this fallback is only for the demo.
    return RequestStateCodec(os.environ.get(
        "MCP_STATE_SECRET", "task-1-demo-secret-change-me").encode())
