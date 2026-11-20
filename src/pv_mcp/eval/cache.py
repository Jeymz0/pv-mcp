"""Disk cache for chat-model replies. A repeated case does not spend the quota again."""

import hashlib
import json
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, message_to_dict


class ResponseCache:
    """Map a hash of the request to the model's reply."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._rows: dict[str, dict[str, Any]] = {}
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._rows = {
                    str(key): value for key, value in loaded.items() if isinstance(value, dict)
                }

    def get(self, key: str) -> AIMessage | None:
        row = self._rows.get(key)
        if row is None:
            return None
        content = row.get("content", "")
        if not isinstance(content, str | list):
            content = ""
        tool_calls = row.get("tool_calls") or []
        if not isinstance(tool_calls, list):
            tool_calls = []
        return AIMessage(content=content, tool_calls=tool_calls)

    def put(self, key: str, message: AIMessage) -> None:
        self._rows[key] = {
            "content": message.content,
            "tool_calls": list(message.tool_calls or []),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._rows, sort_keys=True),
            encoding="utf-8",
        )


def request_key(model_name: str, messages: list[BaseMessage]) -> str:
    """Key includes the model name so a different model does not reuse a reply.

    The message id is left out. The graph assigns a new one on every run, and
    that id is not part of what the model was asked.
    """

    payload = json.dumps(
        [_without_id(message) for message in messages],
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(f"{model_name}\n{payload}".encode()).hexdigest()
    return digest


def _without_id(message: BaseMessage) -> dict[str, Any]:
    payload = message_to_dict(message)
    data = payload.get("data")
    if isinstance(data, dict):
        payload = {**payload, "data": {key: value for key, value in data.items() if key != "id"}}
    return payload


class CachingModel:
    """Call the inner model on a miss and store the reply."""

    def __init__(self, inner: Any, cache: ResponseCache, model_name: str) -> None:
        self.inner = inner
        self.cache = cache
        self.model_name = model_name
        self.hits = 0
        self.misses = 0

    def bind_tools(self, tools: list[Any]) -> "CachingModel":
        return CachingModel(self.inner.bind_tools(tools), self.cache, self.model_name)

    async def ainvoke(self, messages: list[BaseMessage]) -> AIMessage:
        key = request_key(self.model_name, messages)
        cached = self.cache.get(key)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        reply = await self.inner.ainvoke(messages)
        if not isinstance(reply, AIMessage):
            reply = AIMessage(content=getattr(reply, "content", "") or "")
        self.cache.put(key, reply)
        return reply
