"""The HTTP client retries, and it never returns the API key."""

from collections.abc import Iterator

import httpx
import pytest
import respx
from mcp.server.mcpserver.exceptions import ToolError
from tests.conftest import FIXED

from pv_mcp.openfda.client import OpenFdaClient


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.mark.anyio
async def test_retries_a_503_then_returns_counts(router: respx.MockRouter) -> None:
    route = router.get("https://api.fda.gov/drug/event.json").mock(
        side_effect=[
            httpx.Response(503, json={"error": {"code": "SERVER"}}),
            httpx.Response(200, json={"results": [{"term": "NAUSEA", "count": 3}]}),
        ]
    )
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    async with httpx.AsyncClient(base_url="https://api.fda.gov") as http:
        client = OpenFdaClient(
            http,
            base_url="https://api.fda.gov",
            api_key="super-secret-key",
            clock=lambda: FIXED,
            label_max_chars=4000,
            sleeper=sleeper,
        )
        result = await client.top_reactions(drug="ibuprofen", limit=5)

    assert result.reactions[0].reaction == "NAUSEA"
    assert result.reactions[0].count == 3
    assert result.disclaimer.startswith("FAERS reports do not establish")
    assert len(route.calls) == 2
    assert sleeps == [0.25]
    assert route.calls[0].request.url.params["api_key"] == "super-secret-key"
    assert "super-secret-key" not in result.source.url
    assert "api_key" not in result.source.url


@pytest.mark.anyio
async def test_timeout_becomes_a_tool_error(router: respx.MockRouter) -> None:
    router.get("https://api.fda.gov/drug/event.json").mock(
        side_effect=httpx.TimeoutException("slow")
    )

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
        )
        with pytest.raises(ToolError, match="timeout"):
            await client.search_adverse_events(
                drug="ibuprofen",
                reaction=None,
                serious_only=False,
                date_from=None,
                date_to=None,
                limit=1,
            )
