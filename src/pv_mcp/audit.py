"""One JSON line per tool call. Secrets and the bearer token are never written."""

import json
import time
from collections.abc import Mapping
from typing import Any, TextIO

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.types import CallToolResult
from pydantic import BaseModel

_SECRET_KEYS = frozenset(
    {"token", "api_key", "authorization", "password", "secret", "pv_mcp_token", "openfda_api_key"}
)
_MAX_STRING = 200


class AuditLog:
    """Append-only JSONL log. stdio reserves stdout for MCP, so the default is stderr."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write(self, record: Mapping[str, object]) -> None:
        self._stream.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")
        self._stream.flush()


class AuditMiddleware:
    """Record every tools/call, including those the rate limiter refuses."""

    def __init__(self, log: AuditLog) -> None:
        self._log = log

    async def __call__(
        self,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        if ctx.method != "tools/call":
            return await call_next(ctx)
        started = time.perf_counter()
        status = "error"
        result: HandlerResult = None
        try:
            result = await call_next(ctx)
            status = "error" if _is_error(result) else "ok"
            return result
        finally:
            self._log.write(
                {
                    "event": "tool_call",
                    "caller": caller_id(),
                    "tool": _tool_name(ctx.params),
                    "params": _params(ctx.params),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "status": status,
                    "result_size": _result_size(result),
                }
            )


def caller_id() -> str:
    """HTTP caller is the token's client id. stdio has no token, so it is local."""

    access = get_access_token()
    if access is None or not access.client_id:
        return "local"
    return access.client_id


def _tool_name(params: Mapping[str, Any] | None) -> str:
    if params is None:
        return ""
    name = params.get("name")
    return name if isinstance(name, str) else ""


def _params(params: Mapping[str, Any] | None) -> object:
    if params is None:
        return {}
    arguments = params.get("arguments")
    return _redact(arguments if arguments is not None else {})


def _redact(value: object) -> object:
    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in _SECRET_KEYS:
                redacted[key_text] = "[redacted]"
            else:
                redacted[key_text] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and len(value) > _MAX_STRING:
        return value[:_MAX_STRING] + "…"
    return value


def _is_error(result: object) -> bool:
    if isinstance(result, CallToolResult):
        return bool(result.is_error)
    if isinstance(result, Mapping):
        return bool(result.get("isError", result.get("is_error")))
    return False


def _result_size(result: object) -> int:
    if isinstance(result, BaseModel):
        return len(result.model_dump_json())
    if result is None:
        return 0
    try:
        return len(json.dumps(result))
    except TypeError:
        return 0
