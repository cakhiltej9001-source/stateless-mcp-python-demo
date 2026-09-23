"""Small server comparing stateful and stateless MCP flows."""

import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


STATEFUL_VERSION = "2025-11-25"
STATELESS_VERSION = "2026-07-28"
SESSIONS = {}


def result(request_id, value):
    return {"jsonrpc": "2.0", "id": request_id, "result": value}


def handle(request, session_id=None):
    """Return (HTTP status, JSON body, new session ID)."""
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    # Stateful flow: initialize and remember a server-side session.
    if method == "initialize":
        session_id = uuid.uuid4().hex[:8]
        SESSIONS[session_id] = {"initialized": False}
        return 200, result(request_id, {
            "protocolVersion": STATEFUL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "simple-mcp-demo", "version": "1.0"},
        }), session_id

    if method == "notifications/initialized":
        if session_id not in SESSIONS:
            raise ValueError("Unknown stateful session")
        SESSIONS[session_id]["initialized"] = True
        return 202, None, None

    # The presence of a session ID selects the older stateful path.
    if session_id:
        if not SESSIONS.get(session_id, {}).get("initialized"):
            raise ValueError("Complete the initialization handshake first")
        name = params.get("arguments", {}).get("name", "friend")
        return 200, result(request_id, {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"Hello, {name}!"}],
        }), None

    # Stateless flow: every retry repeats the tool arguments and user input.
    if method == "tools/call" and params.get("name") == "greet":
        name = params.get("arguments", {}).get("name", "friend")
        answer = params.get("inputResponses", {}).get("confirm")

        if answer is None:
            value = {
                "resultType": "input_required",
                "inputRequests": {
                    "confirm": {
                        "method": "elicitation/create",
                        "params": {"message": f"Greet {name}?"},
                    }
                },
            }
        elif (
            answer.get("action") == "accept"
            and answer.get("content", {}).get("confirmed") is True
        ):
            value = {
                "resultType": "complete",
                "content": [{"type": "text", "text": f"Hello, {name}!"}],
            }
        else:
            value = {
                "resultType": "complete",
                "content": [{"type": "text", "text": "Greeting cancelled."}],
            }
        return 200, result(request_id, value), None

    return 404, {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }, None


class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        if self.path != "/mcp":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            version = self.headers.get("MCP-Protocol-Version")
            if version not in {STATEFUL_VERSION, STATELESS_VERSION}:
                raise ValueError("Unsupported MCP protocol version")
            status, response, new_session = handle(
                request, self.headers.get("Mcp-Session-Id")
            )
        except (ValueError, json.JSONDecodeError) as error:
            status, new_session = 400, None
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": str(error)},
            }

        body = b"" if response is None else json.dumps(response, indent=2).encode()
        self.send_response(status)
        if new_session:
            self.send_header("Mcp-Session-Id", new_session)
        if body:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, message, *args):
        print("[server]", message % args)


if __name__ == "__main__":
    print("Server running at http://127.0.0.1:8000/mcp")
    ThreadingHTTPServer(("127.0.0.1", 8000), MCPHandler).serve_forever()
