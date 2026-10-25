"""openFDA responses are cached without the API key, and they expire."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.mcpserver.exceptions import ToolError

from pv_mcp.cache import ResponseCache, cache_key
from pv_mcp.openfda.client import OpenFdaClient
from tests.conftest import FIXED

COUNTS = {"results": [{"term": "NAUSEA", "count": 3}]}


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as mock:
        yield mock


def test_cache_key_ignores_parameter_order() -> None:
    left = cache_key("/drug/event.json", {"limit": "5", "search": "a"})
    right = cache_key("/drug/event.json", {"search": "a", "limit": "5"})
    assert left == right
    assert left != cache_key("/drug/event.json", {"search": "a", "limit": "5", "api_key": "secret"})


def test_expired_rows_are_dropped(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "openfda.sqlite", ttl_seconds=10)
    start = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)
    cache.put("k", 200, b"{}", "2026-10-25T08:00:00+00:00", now=start)
    assert cache.get("k", now=start) is not None
    assert cache.get("k", now=start + timedelta(seconds=10)) is None
    cache.close()


@pytest.mark.anyio
async def test_second_call_reuses_the_original_retrieval_time(
    router: respx.MockRouter, tmp_path: Path
) -> None:
    route = router.get("https://api.fda.gov/drug/event.json").mock(
        return_value=httpx.Response(200, json=COUNTS)
    )
    cache = ResponseCache(tmp_path / "openfda.sqlite", ttl_seconds=3600)
    current = {"now": FIXED}

    async with httpx.AsyncClient(base_url="https://api.fda.gov") as http:
        client = OpenFdaClient(
            http,
            base_url="https://api.fda.gov",
            api_key="super-secret-key",
            clock=lambda: current["now"],
            label_max_chars=4000,
            cache=cache,
        )
        first = await client.top_reactions(drug="ibuprofen", limit=5)
        current["now"] = FIXED + timedelta(minutes=5)
        second = await client.top_reactions(drug="ibuprofen", limit=5)
    cache.close()

    assert len(route.calls) == 1
    assert first.source.cached is False
    assert second.source.cached is True
    assert second.source.retrieved_at == "2026-10-25T08:00:00+00:00"
    assert "super-secret-key" not in second.source.url
    assert second.reactions[0].count == 3


@pytest.mark.anyio
async def test_a_different_api_key_still_hits_the_same_row(
    router: respx.MockRouter, tmp_path: Path
) -> None:
    route = router.get("https://api.fda.gov/drug/event.json").mock(
        return_value=httpx.Response(200, json=COUNTS)
    )
    cache = ResponseCache(tmp_path / "openfda.sqlite", ttl_seconds=3600)
    async with httpx.AsyncClient(base_url="https://api.fda.gov") as http:
        first = OpenFdaClient(
            http,
            base_url="https://api.fda.gov",
            api_key="key-one",
            clock=lambda: FIXED,
            label_max_chars=4000,
            cache=cache,
        )
        second = OpenFdaClient(
            http,
            base_url="https://api.fda.gov",
            api_key="key-two",
            clock=lambda: FIXED,
            label_max_chars=4000,
            cache=cache,
        )
        await first.top_reactions(drug="ibuprofen", limit=5)
        result = await second.top_reactions(drug="ibuprofen", limit=5)
    cache.close()

    assert len(route.calls) == 1
    assert result.source.cached is True
    assert route.calls[0].request.url.params["api_key"] == "key-one"


@pytest.mark.anyio
async def test_server_errors_are_not_cached(router: respx.MockRouter, tmp_path: Path) -> None:
    route = router.get("https://api.fda.gov/drug/event.json").mock(
        return_value=httpx.Response(503, json={"error": {"code": "SERVER"}})
    )
    cache = ResponseCache(tmp_path / "openfda.sqlite", ttl_seconds=3600)

    async def sleeper(_delay: float) -> None:
        return None

    async with httpx.AsyncClient(base_url="https://api.fda.gov") as http:
        client = OpenFdaClient(
            http,
            base_url="https://api.fda.gov",
            api_key=None,
            clock=lambda: FIXED,
            label_max_chars=4000,
            sleeper=sleeper,
            cache=cache,
        )
        with pytest.raises(ToolError, match="HTTP 503"):
            await client.top_reactions(drug="ibuprofen", limit=5)
        with pytest.raises(ToolError, match="HTTP 503"):
            await client.top_reactions(drug="ibuprofen", limit=5)
    cache.close()

    assert len(route.calls) == 6
