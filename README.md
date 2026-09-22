# 🔌 Stateless MCP — Task 1

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-2026--07--28-7C3AED)](https://modelcontextprotocol.io/)
[![Tests](https://img.shields.io/badge/tests-3%20passing-2EA44F)](#automated-verification)

![MCP basics sticker](https://img.shields.io/badge/%F0%9F%A7%A0-MCP%20basics-2563EB?style=for-the-badge)
![Handshake sticker](https://img.shields.io/badge/%F0%9F%A4%9D-Handshake-F59E0B?style=for-the-badge)
![Stateless flow sticker](https://img.shields.io/badge/%F0%9F%9A%80-Stateless%20flow-16A34A?style=for-the-badge)

A dependency-free Python implementation of the stateless-first concepts in
[SEP-2575: Make MCP Stateless](https://modelcontextprotocol.io/seps/2575-stateless-mcp).
It demonstrates per-request negotiation, capability discovery, elicitation,
multi-round-trip requests, signed request state, and final special responses.

> 🧩 **Learning path:** What is MCP? → How the older handshake works → Why
> stateless MCP? → Run the demo → Practice interview questions.

## 🧠 What is MCP?

**Model Context Protocol (MCP)** is a standard way for an AI application to
connect to external tools and information. An MCP **host** (for example, an AI
assistant app) runs an MCP **client** that communicates with an MCP **server**.
The server can expose:

| Building block | What it provides | Simple example |
|---|---|---|
| 🛠️ **Tools** | Actions the model can request | `confirm_operation` |
| 📚 **Resources** | Data the application can read | A document or database record |
| 🧾 **Prompts** | Reusable prompt templates | A code review prompt |

MCP messages use JSON-RPC 2.0. The transport carries those messages, commonly
over standard input/output (`stdio`) or Streamable HTTP. In this repository the
client calls a tool over HTTP and the server asks the person for confirmation
before returning a result. See the [MCP protocol overview](https://modelcontextprotocol.io/specification/2026-07-28/basic/index).

## 🤝 How the older stateful handshake works

In the **2025-11-25 protocol revision**, the client and server establish their
shared protocol context before normal tool calls. This was the required
initialization sequence for that revision:

```text
MCP client                              MCP server
    │                                       │
    │  1. initialize                        │
    │     version + client capabilities     │
    ├──────────────────────────────────────>│
    │  2. initialize result                 │
    │     version + server capabilities     │
    │<──────────────────────────────────────┤
    │  3. notifications/initialized         │
    ├──────────────────────────────────────>│
    │  4. tools/list, tools/call, ...       │
    ├──────────────────────────────────────>│
```

The client starts by proposing a protocol version and announcing features it
supports, such as form elicitation. The server replies with the version it
selected, its capabilities, and implementation information. The client then
sends `notifications/initialized` to say it is ready. Subsequent operations
use that negotiated context. A server may also establish a transport session;
when it does, later requests can depend on the server instance holding that
session. The [2025 lifecycle specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
defines the exact sequence.

> 📌 **Interview distinction:** “Stateful” here describes protocol context
> retained across requests. The three-step initialization and a transport
> session are related but not identical concepts.

## 🚀 Why stateless MCP?

The older initialization model makes later requests depend on information
exchanged earlier. If a server stores that context locally, a load balancer may
need to send the client's later requests back to the same instance. A restart
can also require reconnecting and initializing again.

The **2026-07-28 protocol revision** removes the mandatory initialization
handshake. Each request carries its protocol version and client capabilities;
`server/discover` supplies server information when needed. For an interactive
step such as elicitation, the server returns `input_required`; the client
collects the input and retries the original call. This allows independent
workers to understand each request without a session-specific route. See
[SEP-2575](https://modelcontextprotocol.io/seps/2575-stateless-mcp) and the
[current message model](https://modelcontextprotocol.io/specification/2026-07-28/basic/index).

| Stateful concern | Stateless approach in this project |
|---|---|
| Initialization handshake | Version and capabilities travel with every request |
| Server-side session memory | Signed `requestState` is echoed by the client |
| Mid-call server request | `input_required` embeds `elicitation/create` |
| Resume a broken exchange | Client retries with a new JSON-RPC request ID |

## 🗺️ Architecture

```text
Client                                      Stateless server
  │ tools/call: id=1 + metadata/capabilities       │
  ├────────────────────────────────────────────────>│
  │       input_required + elicitation + state      │
  │<────────────────────────────────────────────────┤
  │ collect human confirmation                      │
  │ tools/call: id=2 + response + echoed state      │
  ├────────────────────────────────────────────────>│
  │                     complete result              │
  │<────────────────────────────────────────────────┤
```

## ✨ Implemented concepts

- `server/discover` for versions and server capabilities.
- Required `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` headers.
- Per-request protocol version, client identity, and capabilities in `_meta`.
- Form elicitation through an embedded `elicitation/create` request.
- `resultType: "input_required"` followed by `resultType: "complete"`.
- HMAC-SHA256 signed, expiring `requestState` bound to tool arguments.
- Errors for mismatched headers, unsupported versions, missing capabilities,
  malformed requests, modified state, and unknown methods.

## 📸 Output walkthrough

### 1. Server requests input

![Round 1 input-required response](assets/round-1-input-required.png)

The initial `tools/call` does not block while waiting for the user. The server
returns an `input_required` result containing an elicitation schema and a signed,
opaque `requestState`, then finishes the HTTP exchange.

### 2. Client retries and completes

![Round 2 complete response](assets/round-2-complete.png)

After confirmation, the client sends a new JSON-RPC request containing the same
tool arguments, the elicitation answer, and the byte-for-byte state token. The
server verifies both state integrity and argument binding before completing.

### Automated verification

![Passing test suite](assets/tests-passing.png)

The tests verify the successful two-round flow, capability enforcement, and
rejection of a modified `requestState` token.

## ▶️ Run locally

The Task 1 implementation uses only Python's standard library.

Start the server:

```powershell
$env:MCP_STATE_SECRET = "replace-with-a-long-random-secret"
python server.py
```

In another terminal, start the client:

```powershell
python demo_client.py
```

Answer `y` at the confirmation prompt. Then run the tests:

```powershell
python -m unittest discover -s tests -v
```

## ⏳ In-flight rules

1. A 2026 server does not push `elicitation/create` as a separate JSON-RPC
   request during a tool call. It embeds the request in an `input_required`
   result and finishes that HTTP exchange.
2. The retry is a new request with a new request ID. It repeats the original
   method and arguments and includes only the current round's `inputResponses`.
3. Any cross-round knowledge travels in `requestState`, never in server memory.
   Because clients can inspect or modify that value, it must be integrity
   protected, short-lived, and bound to the original operation.
4. The server may only request features declared in that request's client
   capabilities. It cannot remember capabilities from an earlier request.
5. Closing an HTTP response stream cancels that in-flight request. Broken
   streams are not resumed; the client issues a new request instead.

## 🎤 Common interview questions with worked answers

<details>
<summary><strong>1. What problem does MCP solve?</strong></summary>

**Answer:** MCP gives AI applications a common client-server interface for
discovering tools, reading resources, and using prompt templates. A host can
connect to different servers through the same message model instead of writing
a separate integration contract for each service.

**Example:** This server advertises `confirm_operation` through `tools/list`;
the client invokes it through `tools/call`.

</details>

<details>
<summary><strong>2. What are the three messages in the older initialization handshake?</strong></summary>

**Answer:** In the `2025-11-25` revision: the client sends `initialize` with its
version and capabilities; the server returns its chosen version and
capabilities; the client sends `notifications/initialized`. Normal operations
follow after this exchange.

**How to explain it:** “Request, response, ready notification.”

</details>

<details>
<summary><strong>3. What changes in stateless MCP?</strong></summary>

**Answer:** In `2026-07-28`, there is no mandatory initialization handshake.
Version and client capabilities travel with each request. The server can be
discovered using `server/discover`, and each request can be processed without
remembering an earlier negotiation.

**In this code:** `stateless_mcp.py` checks `_meta` and the matching HTTP
version header for every request.

</details>

<details>
<summary><strong>4. Why can a stateless server scale more easily behind a load balancer?</strong></summary>

**Answer:** A later request does not need to reach the same worker that handled
the previous one. It contains the current version, capabilities, arguments,
and any explicit state required for that operation.

**Production solution:** Share a strong `requestState` signing key across
workers so another worker can validate the retry. Authenticate every request.

</details>

<details>
<summary><strong>5. What is elicitation, and how does it work here?</strong></summary>

**Answer:** Elicitation asks a person for information that the tool cannot
safely infer, such as confirmation. The server embeds an `elicitation/create`
form request inside an `input_required` result. The client shows it, captures
the answer, and retries `tools/call` with `inputResponses`.

**Try it:** Run `python demo_client.py` and answer `y` at the prompt.

</details>

<details>
<summary><strong>6. Is <code>input_required</code> an error?</strong></summary>

**Answer:** No. It is an intermediate result saying the server needs input to
finish the operation. Once the client supplies that input in a new request,
the server returns `resultType: "complete"`.

**Debugging tip:** Check `resultType` before treating the response as final.

</details>

<details>
<summary><strong>7. What must a client include when retrying after elicitation?</strong></summary>

**Answer:** The original method and arguments, a fresh JSON-RPC request ID,
the answers in `inputResponses`, and the exact opaque `requestState` when the
server provided one. The request also needs its per-request metadata again.

**In this demo:** Round 1 uses ID `1`; Round 2 uses ID `2`.

</details>

<details>
<summary><strong>8. Why sign <code>requestState</code>?</strong></summary>

**Answer:** The token travels through the client, so the server must assume it
could be modified. A signature detects tampering. The token should expire and
be bound to the original operation, arguments, and authenticated caller where
applicable.

**In this code:** `RequestStateCodec` uses HMAC-SHA256 and an expiry; the tool
checks that the token's operation matches the retried arguments. The tampering
test expects a `-32602` error.

</details>

<details>
<summary><strong>9. What happens if the client did not declare elicitation support?</strong></summary>

**Answer:** The server must not assume the client can display a form. If the
tool requires it, the server returns a missing-capability error. The client
must declare the capability on the request that needs it.

**In this code:** The test sends empty capabilities and checks for `-32021`.

</details>

<details>
<summary><strong>10. Does stateless MCP mean an application can never store state?</strong></summary>

**Answer:** No. It means the protocol does not require hidden per-client
session state for every request. An application can still use a database or
explicit state handle when its feature needs one. The handle or other required
context must be available to a worker processing the next request.

**Example:** This demo carries short-lived cross-round context in signed
`requestState` rather than server memory.

</details>

## 📁 Project structure

```text
.
├── assets/                       # Generated output evidence
├── scripts/generate_screenshots.py
├── tests/test_stateless_mcp.py   # Protocol and security tests
├── stateless_mcp.py              # Stateless MCP core
├── server.py                     # HTTP entry point
├── demo_client.py                # Interactive two-round client
├── client.py                     # Short compatibility entry point
└── README.md
```

## 🔐 Security notes

- Set `MCP_STATE_SECRET` to a long random secret outside local demonstrations.
- Share the same secret across replicas so any worker can validate a retry.
- Keep tokens short-lived and bind them to the original method and arguments.
- Treat `inputResponses` and `requestState` as untrusted client input.
- Authenticate and authorize every request independently in production.

## 📖 References

- [MCP 2026-07-28 overview](https://modelcontextprotocol.io/specification/2026-07-28/basic/index)
- [MCP 2025-11-25 lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [SEP-2575: Make MCP Stateless](https://modelcontextprotocol.io/seps/2575-stateless-mcp)
- [MCP 2026-07-28 tool and input-required specification](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## 🧪 Scope

This is an educational wire-level implementation focused on Task 1. Production
servers should use an official MCP SDK for complete schema validation, SSE,
authentication, subscriptions, cancellation, and compatibility behavior.
