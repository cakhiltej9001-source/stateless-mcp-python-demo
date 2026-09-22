import unittest

from stateless_mcp import PROTOCOL_VERSION, RequestStateCodec, handle_rpc


class StatelessMCPTests(unittest.TestCase):
    def setUp(self):
        self.codec = RequestStateCodec(b"test-secret")
        self.headers = {
            "mcp-protocol-version": PROTOCOL_VERSION,
            "mcp-method": "tools/call",
            "mcp-name": "confirm_operation",
        }
        self.params = {
            "name": "confirm_operation",
            "arguments": {"operation": "ship release"},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
            },
        }

    def request(self, request_id, params):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": params,
        }

    def test_elicitation_then_retry_completes_without_server_session(self):
        status, first = handle_rpc(self.request(1, self.params), self.headers, self.codec)
        self.assertEqual(status, 200)
        self.assertEqual(first["result"]["resultType"], "input_required")

        retry = dict(self.params)
        retry["requestState"] = first["result"]["requestState"]
        retry["inputResponses"] = {
            "confirm": {"action": "accept", "content": {"confirmed": True}}
        }
        status, second = handle_rpc(self.request(2, retry), self.headers, self.codec)
        self.assertEqual(status, 200)
        self.assertEqual(second["result"]["resultType"], "complete")
        self.assertFalse(second["result"]["isError"])

    def test_tampered_state_is_rejected(self):
        _, first = handle_rpc(self.request(1, self.params), self.headers, self.codec)
        retry = dict(self.params)
        retry["requestState"] = first["result"]["requestState"] + "tampered"
        retry["inputResponses"] = {
            "confirm": {"action": "accept", "content": {"confirmed": True}}
        }
        status, response = handle_rpc(self.request(2, retry), self.headers, self.codec)
        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], -32602)

    def test_missing_elicitation_capability_is_rejected(self):
        params = dict(self.params)
        params["_meta"] = dict(self.params["_meta"])
        params["_meta"]["io.modelcontextprotocol/clientCapabilities"] = {}
        status, response = handle_rpc(self.request(1, params), self.headers, self.codec)
        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], -32021)


if __name__ == "__main__":
    unittest.main()
