"""
TASK 1 - STATELESS MCP + ELICITATION DEMO
-----------------------------------------

This MCP server exposes a demo tool called provision_database.

The model supplies the database name, but the server asks the human to choose
the cloud region. This prevents the model from guessing an important value.

No real AWS, Azure, or Google Cloud resource is created.
"""

import argparse
from typing import Annotated

from pydantic import BaseModel, Field

from mcp.server import MCPServer
from mcp.server.mcpserver import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
    Elicit,
    ElicitationResult,
    Resolve,
)


# MCPServer is the high-level server class in MCP Python SDK v2.
mcp = MCPServer("Stateless MCP Database Demo")


class RegionChoice(BaseModel):
    """Structured form data that must be provided by the human."""

    region: str = Field(
        description="Cloud deployment region. Example: ap-south-1"
    )


async def ask_region() -> Elicit[RegionChoice]:
    """
    Ask the human which cloud region should be used.

    Returning Elicit tells the SDK that this value is missing. For modern
    stateless MCP, the SDK returns an input-required result and resumes the
    tool after the client supplies a validated RegionChoice.
    """

    return Elicit(
        "Which cloud region should the database be deployed in?",
        RegionChoice,
    )


@mcp.tool()
async def provision_database(
    # The model/client supplies this normal tool argument.
    name: str,
    # Resolve hides this parameter from the model-facing input schema.
    # The SDK runs ask_region() and injects the human's result.
    region_choice: Annotated[
        ElicitationResult[RegionChoice],
        Resolve(ask_region),
    ],
) -> str:
    """
    Simulate database provisioning after human-in-the-loop elicitation.

    This function returns text only; it never creates cloud infrastructure.
    """

    if isinstance(region_choice, AcceptedElicitation):
        region = region_choice.data.region
        return (
            f"Demo database '{name}' was successfully provisioned "
            f"in region '{region}'."
        )

    if isinstance(region_choice, DeclinedElicitation):
        return (
            "Database was not provisioned because "
            "the user declined to provide a region."
        )

    if isinstance(region_choice, CancelledElicitation):
        return "Database provisioning was cancelled."

    return "Database provisioning did not complete."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MCP database demo.")
    parser.add_argument(
        "--mode",
        choices=("stateless", "stateful"),
        default="stateless",
        help="Use modern stateless HTTP by default or the legacy session flow.",
    )
    args = parser.parse_args()

    # Streamable HTTP endpoint: http://127.0.0.1:8000/mcp
    # In stateful mode, the SDK keeps a session and a request-scoped channel
    # for legacy server-to-client elicitation.
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000,
        stateless_http=args.mode == "stateless",
        json_response=args.mode == "stateless",
    )
