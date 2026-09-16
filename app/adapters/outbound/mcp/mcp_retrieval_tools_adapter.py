from typing import Any

from app.adapters.outbound.mcp.mcp_http_client import McpHttpClient


class McpRetrievalToolsAdapter:
    """Implements RetrievalToolsProviderPort via clinyq-mcp-azure-search.

    `tenant_id` is bound at construction and injected into every tool call --
    the LLM never sees or supplies it (stripped out of the schemas returned to
    it too), same treatment tenant_id already gets in every other tenant-bound
    outbound adapter in this codebase (e.g. AzureSearchPriceCatalogAdapter).
    """

    _HIDDEN_PARAMS = {"tenant_id"}

    def __init__(self, *, mcp_client: McpHttpClient, tenant_id: str):
        self._client = mcp_client
        self._tenant_id = tenant_id

    async def get_tool_schemas(self) -> list[dict]:
        tools = await self._client.list_tools()
        return [self._to_openai_schema(tool) for tool in tools]

    def _to_openai_schema(self, tool: dict) -> dict:
        input_schema = tool.get("inputSchema", {})
        properties = {
            name: schema
            for name, schema in input_schema.get("properties", {}).items()
            if name not in self._HIDDEN_PARAMS
        }
        required = [name for name in input_schema.get("required", []) if name not in self._HIDDEN_PARAMS]

        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    async def call_tool(self, name: str, arguments: dict) -> Any:
        return await self._client.call_tool(name, {**arguments, "tenant_id": self._tenant_id})
