"""
TASK 1 - MCP CLIENT
-------------------

This client connects to the server, discovers its tools, calls
provision_database, handles the elicitation request, asks the human for a
region, and prints the final result.
"""

import argparse
import anyio
import sys

from mcp import Client
from mcp.client import ClientRequestContext
from mcp.types import (
    ElicitRequestParams,
    ElicitRequestURLParams,
    ElicitResult,
    TextContent,
)

# Keep the decorative status output readable in redirected Windows consoles too.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def handle_elicitation(
    context: ClientRequestContext,
    params: ElicitRequestParams,
) -> ElicitResult:
    """
    Display an MCP elicitation request and return the human's answer.

    One callback handles both URL and form elicitation. This demo needs only
    form elicitation, so URL requests are printed and cancelled safely.
    """

    # URL elicitation is used for out-of-band flows such as OAuth or payment.
    if isinstance(params, ElicitRequestURLParams):
        print("\n🌐 Server requested URL interaction:")
        print(params.url)
        return ElicitResult(action="cancel")

    print("\n🤖 MCP server needs additional information:")
    print(params.message)

    region = input(
        "\nEnter region (example: ap-south-1) or type 'cancel': "
    ).strip()

    if region.lower() == "cancel":
        return ElicitResult(action="cancel")

    if not region:
        print("⚠️ No region entered. Cancelling.")
        return ElicitResult(action="cancel")

    # The content keys must match the server-side RegionChoice model.
    return ElicitResult(
        action="accept",
        content={"region": region},
    )


async def main(mode: str) -> None:
    """Connect to the MCP server and run the elicitation workflow."""

    async with Client(
        "http://127.0.0.1:8000/mcp",
        # "auto" negotiates the modern stateless protocol.
        # "legacy" explicitly performs initialize/initialized first.
        mode="legacy" if mode == "stateful" else "auto",
        elicitation_callback=handle_elicitation,
    ) as client:
        print("\n✅ Connected to MCP server")
        print("🔄 Demo mode:", mode)
        print("📡 Protocol version:", client.protocol_version)

        tools_result = await client.list_tools()
        print("\n🔧 Available MCP tools:")
        for tool in tools_result.tools:
            print(f"- {tool.name}: {tool.description}")

        print("\n🚀 Calling provision_database...")

        # Only name is model supplied. The hidden resolver parameter asks
        # the human for region through MCP elicitation.
        result = await client.call_tool(
            "provision_database",
            {"name": "orders-db"},
        )

        print("\n✅ Final MCP result:")
        for block in result.content:
            if isinstance(block, TextContent):
                print(block.text)
            else:
                print(block)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MCP client demo.")
    parser.add_argument(
        "mode",
        choices=("stateless", "stateful"),
        nargs="?",
        default="stateless",
        help="Choose modern stateless flow or the legacy initialization handshake.",
    )
    args = parser.parse_args()
    anyio.run(main, args.mode)
