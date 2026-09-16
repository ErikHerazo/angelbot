from app.adapters.outbound.mcp.mcp_retrieval_tools_adapter import McpRetrievalToolsAdapter


class FakeMcpClient:
    def __init__(self, tools: list[dict], call_result=None):
        self._tools = tools
        self._call_result = call_result
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self) -> list[dict]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return self._call_result


RAW_TOOL = {
    "name": "search_price_catalog",
    "description": "Search prices",
    "inputSchema": {
        "type": "object",
        "properties": {"tenant_id": {"type": "string"}, "query": {"type": "string"}},
        "required": ["tenant_id", "query"],
    },
}


async def test_get_tool_schemas_strips_tenant_id():
    fake_client = FakeMcpClient(tools=[RAW_TOOL])
    adapter = McpRetrievalToolsAdapter(mcp_client=fake_client, tenant_id="agb")

    schemas = await adapter.get_tool_schemas()

    assert schemas == [
        {
            "type": "function",
            "function": {
                "name": "search_price_catalog",
                "description": "Search prices",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
    ]


async def test_call_tool_injects_tenant_id():
    fake_client = FakeMcpClient(tools=[], call_result=[{"procedure_name": "RINOPLASTIA"}])
    adapter = McpRetrievalToolsAdapter(mcp_client=fake_client, tenant_id="agb")

    result = await adapter.call_tool("search_price_catalog", {"query": "nariz"})

    assert result == [{"procedure_name": "RINOPLASTIA"}]
    assert fake_client.calls == [("search_price_catalog", {"query": "nariz", "tenant_id": "agb"})]
