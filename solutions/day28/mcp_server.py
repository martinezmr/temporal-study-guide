"""Read-only network tools as an MCP server. Works with any MCP client (Claude Desktop, IDEs, agents).

    uv add mcp
    DEVICE_MODE=live uv run --env-file .env python -m solutions.day28.mcp_server     # stdio transport

Claude Desktop config (claude_desktop_config.json):
    {"mcpServers": {"netops": {"command": "uv", "args": ["run", "--directory", "/Users/manny/Dev/temporal-study-guide",
      "python", "-m", "solutions.day28.mcp_server"]}}}

These tools call the device directly (no Temporal), because MCP tool calls are short, read-only lookups.
Anything that changes a device goes through ProposedRemediationWorkflow (Day 27).
"""

import json

from mcp.server.fastmcp import FastMCP

from solutions.shared import eapi
from solutions.shared.activities import SHOW_ONLY

mcp = FastMCP("netops-readonly")


@mcp.tool()
async def show(device: str, command: str) -> str:
    """Run one read-only EOS 'show ...' command on a lab device and return its text output."""
    if not SHOW_ONLY.match(command.strip()):
        return f"refused: only 'show' commands are allowed, got {command!r}"
    out = (await eapi.run_commands(device, [command.strip()], fmt="text"))[0]
    return out.get("output", json.dumps(out))


@mcp.tool()
async def interfaces(device: str) -> str:
    """Interface link status for one device, as JSON."""
    return json.dumps((await eapi.run_commands(device, ["show interfaces status"]))[0]["interfaceStatuses"])


@mcp.tool()
async def lldp(device: str) -> str:
    """LLDP neighbors for one device, as JSON."""
    return json.dumps((await eapi.run_commands(device, ["show lldp neighbors"]))[0]["lldpNeighbors"])


if __name__ == "__main__":
    mcp.run()
