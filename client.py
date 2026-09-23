"""A minimal client for the stateless MCP demo."""

import json
from urllib.request import Request, urlopen


URL = "http://127.0.0.1:8000/mcp"
PROTOCOL_VERSION = "2026-07-28"


def call(request_id, params):
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": params,
    }
    request = Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        },
        method="POST",
    )
    with urlopen(request) as response:
        return json.load(response)


def main():
    tool_call = {"name": "greet", "arguments": {"name": "Akhil"}}

    first = call(1, tool_call)
    print("\n1. Server asks for input:\n", json.dumps(first, indent=2))

    prompt = first["result"]["inputRequests"]["confirm"]["params"]["message"]
    confirmed = input(f"\n{prompt} [y/N] ").lower() in {"y", "yes"}

    retry = {
        **tool_call,
        "inputResponses": {
            "confirm": {
                "action": "accept",
                "content": {"confirmed": confirmed},
            }
        },
    }
    second = call(2, retry)
    print("\n2. Final result:\n", json.dumps(second, indent=2))


if __name__ == "__main__":
    main()
