"""HTTP client for the openFDA drug event and drug label endpoints."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from pv_mcp.openfda.models import (
    AdverseEventSearchResult,
    LabelSectionName,
    LabelSectionResult,
    SourceReference,
    TopReactionsResult,
)
from pv_mcp.openfda.parsing import parse_event_search, parse_label_section, parse_reaction_counts
from pv_mcp.openfda.queries import (
    REACTION_COUNT_FIELD,
    event_search,
    label_search,
    require_name,
)

_MAX_ATTEMPTS = 3
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_RESPONSE_BYTES = 1_500_000
_EVENT_PATH = "/drug/event.json"
_LABEL_PATH = "/drug/label.json"

Sleeper = Callable[[float], Awaitable[None]]


class OpenFdaClient:
    """Read-only openFDA access with a timeout, a short retry, and a size cap."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str,
        api_key: str | None,
        clock: Callable[[], datetime],
        label_max_chars: int,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._clock = clock
        self._label_max_chars = label_max_chars
        self._sleeper = sleeper

    async def search_adverse_events(
        self,
        *,
        drug: str,
        reaction: str | None,
        serious_only: bool,
        date_from: date | None,
        date_to: date | None,
        limit: int,
    ) -> AdverseEventSearchResult:
        drug_name = require_name(drug, what="drug")
        reaction_name = require_name(reaction, what="reaction") if reaction else None
        today = self._clock().date()
        search = event_search(
            drug=drug_name,
            reaction=reaction_name,
            serious_only=serious_only,
            date_from=date_from,
            date_to=date_to,
            today=today,
        )
        params = {"search": search, "limit": str(limit)}
        payload, source = await self._get_json(_EVENT_PATH, params)
        return parse_event_search(payload, drug=drug_name, source=source)

    async def top_reactions(self, *, drug: str, limit: int) -> TopReactionsResult:
        drug_name = require_name(drug, what="drug")
        search = event_search(
            drug=drug_name,
            reaction=None,
            serious_only=False,
            date_from=None,
            date_to=None,
            today=self._clock().date(),
        )
        params = {"search": search, "count": REACTION_COUNT_FIELD, "limit": str(limit)}
        payload, source = await self._get_json(_EVENT_PATH, params)
        return parse_reaction_counts(payload, drug=drug_name, limit=limit, source=source)

    async def get_label_section(
        self, *, drug: str, section: LabelSectionName
    ) -> LabelSectionResult:
        drug_name = require_name(drug, what="drug")
        params = {"search": label_search(drug_name), "limit": "1", "sort": "effective_time:desc"}
        payload, source = await self._get_json(_LABEL_PATH, params)
        return parse_label_section(
            payload,
            drug=drug_name,
            section=section,
            max_chars=self._label_max_chars,
            source=source,
        )

    async def _get_json(
        self, path: str, params: dict[str, str]
    ) -> tuple[dict[str, object] | None, SourceReference]:
        request_params = dict(params)
        if self._api_key:
            request_params["api_key"] = self._api_key
        response = await self._request(path, request_params)
        source = SourceReference(
            endpoint=path,
            query=params.get("search", ""),
            url=str(httpx.URL(self._base_url).join(path).copy_merge_params(params)),
            retrieved_at=self._clock().astimezone(UTC).isoformat(timespec="seconds"),
        )
        if response.status_code == 404:
            return None, source
        if response.status_code >= 400:
            raise ToolError(f"openFDA returned HTTP {response.status_code}.")
        return _object_payload(response), source

    async def _request(self, path: str, params: dict[str, str]) -> httpx.Response:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._http.get(path, params=params)
            except httpx.TimeoutException as exc:
                if attempt == _MAX_ATTEMPTS:
                    raise ToolError("openFDA did not respond before the timeout.") from exc
                await self._sleeper(0.25 * (2 ** (attempt - 1)))
                continue
            except httpx.HTTPError as exc:
                raise ToolError("The request to openFDA failed.") from exc
            if len(response.content) > _MAX_RESPONSE_BYTES:
                raise ToolError("openFDA returned a response larger than the size cap.")
            if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS:
                await self._sleeper(0.25 * (2 ** (attempt - 1)))
                continue
            return response
        raise ToolError("openFDA did not respond.")


def _object_payload(response: httpx.Response) -> dict[str, object]:
    try:
        payload: object = response.json()
    except ValueError as exc:
        raise ToolError("openFDA returned a body that was not JSON.") from exc
    if not isinstance(payload, dict):
        raise ToolError("openFDA returned an unexpected JSON body.")
    return payload
