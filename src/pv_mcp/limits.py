"""Per-caller sliding window for tool calls."""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.types import CallToolResult, TextContent

from pv_mcp.audit import caller_id


class RateLimiter:
    """Allow `limit` tool calls per caller per window. A limit of 0 disables the check."""

    def __init__(
        self,
        limit: int,
        *,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, caller: str) -> bool:
        if self._limit <= 0:
            return True
        now = self._clock()
        with self._lock:
            hits = self._hits[caller]
            cutoff = now - self._window
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True


class RateLimitMiddleware:
    """Refuse tools/call once the caller is over the window. Other methods pass through."""

    def __init__(self, limiter: RateLimiter) -> None:
        self._limiter = limiter

    async def __call__(
        self,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        if ctx.method == "tools/call" and not self._limiter.allow(caller_id()):
            return CallToolResult(
                content=[
                    TextContent(type="text", text="Rate limit exceeded. Try again shortly."),
                ],
                is_error=True,
            )
        return await call_next(ctx)
