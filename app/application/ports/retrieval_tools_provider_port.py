from typing import Any, Protocol


class RetrievalToolsProviderPort(Protocol):
    async def get_tool_schemas(self) -> list[dict]: ...

    async def call_tool(self, name: str, arguments: dict) -> Any: ...
