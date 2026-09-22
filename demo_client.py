"""Client that automatically drives the demo's elicitation round trip."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from stateless_mcp import PROTOCOL_VERSION


URL = "http://127.0.0.1:8000/mcp"


def call(request_id: int, method: str, params: dict) -> dict:
    params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "task-1-client", "version": "1.0.0"},
        "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
    }
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    headers = {
        "Content-Type": "application/json",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if "name" in params:
        headers["Mcp-Name"] = params["name"]
    request = Request(URL, json.dumps(payload).encode(), headers=headers, method="POST")
    with urlopen(request) as response:
        return json.load(response)


def main() -> None:
    original_params = {
        "name": "confirm_operation",
        "arguments": {"operation": "generate the Task 1 completion report"},
    }
    first = call(1, "tools/call", dict(original_params))
    print("\nRound 1 — server special response:\n", json.dumps(first, indent=2))

    result = first["result"]
    if result["resultType"] != "input_required":
        raise RuntimeError("Expected input_required")
    prompt = result["inputRequests"]["confirm"]["params"]["message"]
    approved = input(f"\n{prompt} [y/N] ").strip().lower() in {"y", "yes"}

    retry_params = dict(original_params)
    retry_params["requestState"] = result["requestState"]
    retry_params["inputResponses"] = {
        "confirm": {"action": "accept", "content": {"confirmed": approved}}
    }
    second = call(2, "tools/call", retry_params)
    print("\nRound 2 — final response:\n", json.dumps(second, indent=2))


if __name__ == "__main__":
    main()
