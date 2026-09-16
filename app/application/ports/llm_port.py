from typing import Any, Optional, Protocol, TypedDict


class LLMToolCall(TypedDict):
    id: str
    name: str
    arguments: dict


class LLMCompletion(TypedDict):
    content: Optional[str]
    tool_calls: Optional[list[LLMToolCall]]


class LLMPort(Protocol):
    async def complete(
        self,
        *,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[Any] = None,
    ) -> LLMCompletion: ...
