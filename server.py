"""A minimal stateless MCP-style JSON-RPC server."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PROTOCOL_VERSION = "2026-07-28"


def handle(request):
    """Process one complete request without storing a client session."""
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "tools/list":
        result = {
            "resultType": "complete",
            "tools": [{
                "name": "greet",
                "description": "Greets a person after confirmation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            }],
        }
    elif method == "tools/call" and params.get("name") == "greet":
        name = params.get("arguments", {}).get("name", "friend")
        answer = params.get("inputResponses", {}).get("confirm", {})

        if not answer:
            result = {
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
            result = {
                "resultType": "complete",
                "content": [{"type": "text", "text": f"Hello, {name}!"}],
            }
        else:
            result = {
                "resultType": "complete",
                "content": [{"type": "text", "text": "Greeting cancelled."}],
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Method not found"},
        }

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        if self.path != "/mcp":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            if self.headers.get("MCP-Protocol-Version") != PROTOCOL_VERSION:
                raise ValueError("Unsupported MCP protocol version")
            response = handle(request)
            status = 200
        except (ValueError, json.JSONDecodeError) as error:
            status = 400
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": str(error)},
            }

        body = json.dumps(response, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, message, *args):
        print("[server]", message % args)


if __name__ == "__main__":
    print("Server running at http://127.0.0.1:8000/mcp")
    ThreadingHTTPServer(("127.0.0.1", 8000), MCPHandler).serve_forever()
