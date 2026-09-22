"""Run the Task 1 stateless MCP demonstration over HTTP."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from stateless_mcp import codec_from_environment, handle_rpc


CODEC = codec_from_environment()


class MCPHandler(BaseHTTPRequestHandler):
    server_version = "StatelessMCPDemo/1.0"

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/mcp":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            headers = {key.lower(): value for key, value in self.headers.items()}
            status, response = handle_rpc(request, headers, CODEC)
        except (ValueError, json.JSONDecodeError):
            status = 400
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }

        body = json.dumps(response, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[server] {format % args}")


if __name__ == "__main__":
    address = ("127.0.0.1", 8000)
    print(f"Stateless MCP demo listening at http://{address[0]}:{address[1]}/mcp")
    ThreadingHTTPServer(address, MCPHandler).serve_forever()
