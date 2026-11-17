"""MCP targets for the summary agent.

stdio launches the server script with the parent environment, so an openFDA
key set in the shell reaches the child. HTTP hands the dev bearer token to a
FastMCP client. The official MCP Python server speaks the initialize handshake,
so the client pins that era instead of probing a newer discovery endpoint.
"""

import os
from pathlib import Path
from typing import Any

from fastmcp.client import Client
from fastmcp.client.transports import PythonStdioTransport

from pv_mcp.agent.settings import AgentSettings


def stdio_server_path() -> Path:
    """Script FastMCP runs under the current interpreter."""

    return Path(__file__).with_name("stdio_server.py")


def mcp_target(settings: AgentSettings) -> Client[Any]:
    """Client the MCPAdapter should wrap. No connection is opened here."""

    if settings.pv_agent_transport == "stdio":
        transport = PythonStdioTransport(
            stdio_server_path(),
            env=dict(os.environ),
            keep_alive=False,
        )
        return Client(transport, mode="legacy")
    url = settings.pv_agent_mcp_url
    if not url.startswith(("http://", "https://")) or not url.endswith("/mcp"):
        raise ValueError("PV_AGENT_MCP_URL must be an http(s) URL ending in /mcp.")
    token = settings.pv_mcp_token
    if token is None:
        raise ValueError("PV_MCP_TOKEN is required when the agent uses HTTP.")
    return Client(url, auth=token.get_secret_value(), mode="legacy")
