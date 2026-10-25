"""In-memory MCP client. No test in this suite contacts openFDA."""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
import respx
from mcp import Client

from pv_mcp.server import build_server
from pv_mcp.settings import Settings

FIXED = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def openfda() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
async def mcp_client(openfda: respx.MockRouter) -> AsyncIterator[Client]:
    settings = Settings(_env_file=None, openfda_api_key=None)
    server = build_server(settings=settings, clock=lambda: FIXED)
    async with Client(server, raise_exceptions=True) as client:
        yield client
