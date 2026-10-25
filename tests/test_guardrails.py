"""Audit lines omit secrets, and the rate limit counts tool calls only."""

import json
from collections.abc import AsyncIterator
from io import StringIO

import httpx
import pytest
import respx
from mcp import Client

from pv_mcp.audit import _redact
from pv_mcp.limits import RateLimiter
from pv_mcp.server import build_server
from pv_mcp.settings import Settings
from tests.conftest import FIXED

COUNTS = {"results": [{"term": "NAUSEA", "count": 3}]}


def test_redacts_secret_keys_and_long_strings() -> None:
    redacted = _redact(
        {
            "api_key": "super-secret-key",
            "drug": "x" * 250,
            "nested": {"Authorization": "Bearer secret"},
        }
    )
    assert isinstance(redacted, dict)
    assert redacted["api_key"] == "[redacted]"
    nested = redacted["nested"]
    assert isinstance(nested, dict)
    assert nested["Authorization"] == "[redacted]"
    drug = redacted["drug"]
    assert isinstance(drug, str)
    assert drug.endswith("…")
    assert "super-secret-key" not in json.dumps(redacted)


def test_sliding_window_is_per_caller() -> None:
    now = {"t": 0.0}
    limiter = RateLimiter(1, window_seconds=60, clock=lambda: now["t"])
    assert limiter.allow("local") is True
    assert limiter.allow("local") is False
    assert limiter.allow("other") is True
    now["t"] = 60.0
    assert limiter.allow("local") is True
    assert RateLimiter(0).allow("local") is True


@pytest.fixture
async def guarded(
    openfda: respx.MockRouter,
) -> AsyncIterator[tuple[Client, StringIO, respx.Route]]:
    route = openfda.get("https://api.fda.gov/drug/event.json").mock(
        return_value=httpx.Response(200, json=COUNTS)
    )
    audit = StringIO()
    settings = Settings(
        _env_file=None,
        openfda_api_key=None,
        openfda_cache_path=None,
        pv_mcp_rate_limit_per_minute=1,
    )
    server = build_server(settings=settings, clock=lambda: FIXED, audit_stream=audit)
    async with Client(server, raise_exceptions=True) as client:
        yield client, audit, route


@pytest.mark.anyio
async def test_audit_records_one_tool_call_and_skips_list(
    guarded: tuple[Client, StringIO, respx.Route],
) -> None:
    client, audit, _route = guarded
    await client.list_tools()
    assert audit.getvalue() == ""
    result = await client.call_tool("top_reactions", {"drug": "ibuprofen", "limit": 1})
    assert result.is_error is False
    lines = [line for line in audit.getvalue().splitlines() if line]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "tool_call"
    assert record["caller"] == "local"
    assert record["tool"] == "top_reactions"
    assert record["params"] == {"drug": "ibuprofen", "limit": 1}
    assert record["status"] == "ok"
    assert record["latency_ms"] >= 0
    assert record["result_size"] > 0


@pytest.mark.anyio
async def test_second_tool_call_is_refused_without_another_openfda_request(
    guarded: tuple[Client, StringIO, respx.Route],
) -> None:
    client, audit, route = guarded
    await client.list_tools()
    first = await client.call_tool("top_reactions", {"drug": "ibuprofen", "limit": 1})
    second = await client.call_tool("top_reactions", {"drug": "ibuprofen", "limit": 1})
    assert first.is_error is False
    assert second.is_error is True
    assert second.content[0].text == "Rate limit exceeded. Try again shortly."
    assert len(route.calls) == 1
    records = [json.loads(line) for line in audit.getvalue().splitlines() if line]
    assert [record["status"] for record in records] == ["ok", "error"]
