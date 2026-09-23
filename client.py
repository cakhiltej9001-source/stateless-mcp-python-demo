"""Run the stateful and stateless MCP demonstrations."""

import argparse
import json
from urllib.request import Request, urlopen


URL = "http://127.0.0.1:8000/mcp"
STATEFUL_VERSION = "2025-11-25"
STATELESS_VERSION = "2026-07-28"


def send(request_id, method, params, version, session_id=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params}
    if request_id is not None:
        payload["id"] = request_id

    headers = {
        "Content-Type": "application/json",
        "MCP-Protocol-Version": version,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    request = Request(
        URL,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urlopen(request) as response:
        body = response.read()
        value = json.loads(body) if body else None
        return value, response.headers.get("Mcp-Session-Id")


def stateful_demo():
    print("\n=== STATEFUL INITIALIZATION HANDSHAKE ===")
    print("1. Client -> initialize")
    initialized, session_id = send(
        1,
        "initialize",
        {
            "protocolVersion": STATEFUL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "demo-client", "version": "1.0"},
        },
        STATEFUL_VERSION,
    )
    print("2. Server -> selected version:", initialized["result"]["protocolVersion"])
    print("   Server created session:", session_id)

    print("3. Client -> notifications/initialized")
    send(None, "notifications/initialized", {}, STATEFUL_VERSION, session_id)

    print("4. Client -> tools/call using the stored session")
    completed, _ = send(
        2,
        "tools/call",
        {"name": "greet", "arguments": {"name": "Akhil"}},
        STATEFUL_VERSION,
        session_id,
    )
    print("5. Server ->", completed["result"]["content"][0]["text"])
    print("Result: later requests depend on server session memory.")


def stateless_demo(auto_confirm=False):
    print("\n=== STATELESS FLOW ===")
    tool_call = {"name": "greet", "arguments": {"name": "Akhil"}}

    print("1. Client -> tools/call (no initialize and no session ID)")
    first, _ = send(1, "tools/call", tool_call, STATELESS_VERSION)
    print("2. Server ->", first["result"]["resultType"])

    prompt = first["result"]["inputRequests"]["confirm"]["params"]["message"]
    confirmed = auto_confirm or input(f"3. {prompt} [y/N] ").lower() in {"y", "yes"}
    if auto_confirm:
        print("3. User confirmation -> yes")

    retry = {
        **tool_call,
        "inputResponses": {
            "confirm": {
                "action": "accept",
                "content": {"confirmed": confirmed},
            }
        },
    }
    print("4. Client -> new self-contained tools/call")
    completed, _ = send(2, "tools/call", retry, STATELESS_VERSION)
    print("5. Server ->", completed["result"]["content"][0]["text"])
    print("Result: no server session is required.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "demo", choices=["stateful", "stateless", "both"], nargs="?", default="both"
    )
    parser.add_argument("--yes", action="store_true", help="auto-confirm the prompt")
    args = parser.parse_args()

    if args.demo in {"stateful", "both"}:
        stateful_demo()
    if args.demo in {"stateless", "both"}:
        stateless_demo(args.yes)


if __name__ == "__main__":
    main()
