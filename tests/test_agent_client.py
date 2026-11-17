"""The agent builds an MCP client and can list this server's tools without calling openFDA."""

import socket
import threading
from pathlib import Path

import pytest
import uvicorn
from fastmcp.client.auth.bearer import BearerAuth
from pydantic import SecretStr

from pv_mcp.agent.connection import mcp_target, stdio_server_path
from pv_mcp.agent.settings import AgentSettings
from pv_mcp.http_transport import transport_security
from pv_mcp.server import build_http_server
from pv_mcp.settings import Settings

TOKEN = "dev-token-value"


def test_stdio_target_launches_the_server_script_in_legacy_mode() -> None:
    settings = AgentSettings(_env_file=None, pv_agent_transport="stdio")
    client = mcp_target(settings)
    assert client.mode == "legacy"
    assert client.transport.script_path == stdio_server_path()
    assert client.transport.keep_alive is False


def test_http_target_carries_the_bearer_token() -> None:
    settings = AgentSettings(
        _env_file=None,
        pv_agent_transport="http",
        pv_agent_mcp_url="http://127.0.0.1:8000/mcp",
        pv_mcp_token=SecretStr(TOKEN),
    )
    client = mcp_target(settings)
    assert client.mode == "legacy"
    assert str(client.transport.url) == "http://127.0.0.1:8000/mcp"
    assert isinstance(client.transport.auth, BearerAuth)
    assert client.transport.auth.token.get_secret_value() == TOKEN


def test_http_target_rejects_a_missing_token_and_a_bad_url() -> None:
    missing = AgentSettings(_env_file=None, pv_agent_transport="http", pv_mcp_token=None)
    with pytest.raises(ValueError, match="PV_MCP_TOKEN"):
        mcp_target(missing)
    bad = AgentSettings(
        _env_file=None,
        pv_agent_transport="http",
        pv_agent_mcp_url="http://127.0.0.1:8000/events",
        pv_mcp_token=SecretStr(TOKEN),
    )
    with pytest.raises(ValueError, match="/mcp"):
        mcp_target(bad)


def test_blank_secrets_and_transport_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "  ")
    monkeypatch.setenv("PV_MCP_TOKEN", " ")
    monkeypatch.setenv("PV_AGENT_TRANSPORT", " HTTP ")
    settings = AgentSettings(_env_file=None)
    assert settings.groq_api_key is None
    assert settings.pv_mcp_token is None
    assert settings.pv_agent_transport == "http"


@pytest.mark.anyio
async def test_adapter_lists_the_three_tools_over_stdio() -> None:
    from langchain.mcp import MCPAdapter

    names = await _tool_names(mcp_target(AgentSettings(_env_file=None, pv_agent_transport="stdio")))
    assert names == {"search_adverse_events", "top_reactions", "get_label_section"}
    assert MCPAdapter is not None


@pytest.mark.anyio
async def test_adapter_lists_the_three_tools_over_http(tmp_path: Path) -> None:
    port = _free_port()
    url = f"http://127.0.0.1:{port}/mcp"
    settings = Settings(
        _env_file=None,
        pv_mcp_token=SecretStr(TOKEN),
        pv_mcp_resource_url=url,
        pv_mcp_http_host="127.0.0.1",
        pv_mcp_http_port=port,
        openfda_cache_path=tmp_path / "cache.sqlite",
    )
    server = build_http_server(settings=settings, cache_path=settings.openfda_cache_path)
    app = server.streamable_http_app(
        host="127.0.0.1",
        transport_security=transport_security(settings),
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    running = uvicorn.Server(config)
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    try:
        while not running.started:
            await _pause()
        client = mcp_target(
            AgentSettings(
                _env_file=None,
                pv_agent_transport="http",
                pv_agent_mcp_url=url,
                pv_mcp_token=SecretStr(TOKEN),
            )
        )
        assert await _tool_names(client) == {
            "search_adverse_events",
            "top_reactions",
            "get_label_section",
        }
    finally:
        running.should_exit = True
        thread.join(timeout=5)


async def _tool_names(client: object) -> set[str]:
    from langchain.mcp import MCPAdapter

    async with MCPAdapter(client) as adapter:  # type: ignore[arg-type]
        tools = await adapter.list_tools()
    return {tool.name for tool in tools}


async def _pause() -> None:
    import anyio

    await anyio.sleep(0.05)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
