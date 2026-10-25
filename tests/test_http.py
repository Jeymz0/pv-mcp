"""Streamable HTTP refuses anonymous callers and still serves the local cache."""

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import StringIO
from pathlib import Path

import httpx
import httpx2
import pytest
import respx
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.transport_security import TransportSecurityMiddleware
from pydantic import SecretStr
from starlette.requests import Request

from pv_mcp.__main__ import main
from pv_mcp.auth import DEV_CLIENT_ID, StaticTokenVerifier
from pv_mcp.http_transport import transport_security
from pv_mcp.server import build_http_server, build_server
from pv_mcp.settings import Settings
from tests.conftest import FIXED

TOKEN = "dev-token-value"
RESOURCE = "http://127.0.0.1:8000/mcp"
COUNTS = {"results": [{"term": "NAUSEA", "count": 3}]}


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        openfda_api_key=SecretStr("super-secret-key"),
        openfda_cache_path=tmp_path / "openfda.sqlite",
        pv_mcp_token=SecretStr(TOKEN),
        pv_mcp_resource_url=RESOURCE,
        pv_mcp_http_host="0.0.0.0",
        pv_mcp_rate_limit_per_minute=60,
    )


def _app(settings: Settings, audit: StringIO) -> object:
    server = build_server(
        settings=settings,
        clock=lambda: FIXED,
        http_auth=True,
        audit_stream=audit,
        cache_path=settings.openfda_cache_path,
    )
    return server.streamable_http_app(
        json_response=True,
        host=settings.pv_mcp_http_host,
        transport_security=transport_security(settings),
    )


@asynccontextmanager
async def _asgi(
    app: object, headers: dict[str, str] | None = None
) -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),  # type: ignore[attr-defined]
        httpx2.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8000",
            headers=headers,
            timeout=httpx2.Timeout(10.0),
        ) as http,
    ):
        yield http


def test_http_entrypoint_exits_when_the_token_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["pv-mcp", "http"])
    monkeypatch.delenv("PV_MCP_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="PV_MCP_TOKEN"):
        main()


def test_http_without_a_token_refuses_to_start() -> None:
    settings = Settings(_env_file=None, pv_mcp_token=None, openfda_cache_path=None)
    with pytest.raises(ValueError, match="PV_MCP_TOKEN"):
        build_http_server(settings=settings)


@pytest.mark.anyio
async def test_verifier_rejects_a_mismatch() -> None:
    verifier = StaticTokenVerifier(TOKEN, resource=RESOURCE)
    assert await verifier.verify_token("nope") is None
    access = await verifier.verify_token(TOKEN)
    assert access is not None
    assert access.client_id == DEV_CLIENT_ID
    assert access.scopes == ["pv:read"]
    assert access.resource == RESOURCE


@pytest.mark.anyio
async def test_binding_all_interfaces_still_rejects_a_foreign_host(tmp_path: Path) -> None:
    security = transport_security(_settings(tmp_path))
    assert "127.0.0.1:*" in security.allowed_hosts
    assert "evil.com" not in security.allowed_hosts
    assert "evil.com:*" not in security.allowed_hosts
    middleware = TransportSecurityMiddleware(security)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [
                (b"host", b"evil.com"),
                (b"content-type", b"application/json"),
            ],
            "path": "/mcp",
        }
    )
    response = await middleware.validate_request(request, is_post=True)
    assert response is not None
    assert response.status_code == 421


@pytest.mark.anyio
async def test_missing_and_wrong_bearer_are_rejected(
    openfda: respx.MockRouter, tmp_path: Path
) -> None:
    app = _app(_settings(tmp_path), StringIO())
    body = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    async with _asgi(app) as http:
        missing = await http.post("/mcp", json=body)
        wrong = await http.post("/mcp", json=body, headers={"Authorization": "Bearer nope"})
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert openfda.calls.call_count == 0


@pytest.mark.anyio
async def test_a_valid_token_calls_openfda_once_and_then_the_cache(
    openfda: respx.MockRouter, tmp_path: Path
) -> None:
    route = openfda.get("https://api.fda.gov/drug/event.json").mock(
        return_value=httpx.Response(200, json=COUNTS)
    )
    audit = StringIO()
    app = _app(_settings(tmp_path), audit)
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/event-stream",
    }
    async with _asgi(app, headers) as http:
        transport = streamable_http_client(RESOURCE, http_client=http)
        async with Client(transport, raise_exceptions=True) as client:
            first = await client.call_tool("top_reactions", {"drug": "ibuprofen", "limit": 1})
            second = await client.call_tool("top_reactions", {"drug": "ibuprofen", "limit": 1})

    assert first.is_error is False
    assert second.is_error is False
    assert isinstance(first.structured_content, dict)
    assert isinstance(second.structured_content, dict)
    assert first.structured_content["source"]["cached"] is False
    assert second.structured_content["source"]["cached"] is True
    assert second.structured_content["source"]["retrieved_at"] == "2026-10-25T08:00:00+00:00"
    assert len(route.calls) == 1
    logged = audit.getvalue()
    assert TOKEN not in logged
    assert "super-secret-key" not in logged
    records = [json.loads(line) for line in logged.splitlines() if line]
    assert [record["caller"] for record in records] == [DEV_CLIENT_ID, DEV_CLIENT_ID]
    assert [record["status"] for record in records] == ["ok", "ok"]
