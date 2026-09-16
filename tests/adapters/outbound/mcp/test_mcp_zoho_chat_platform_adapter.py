from app.adapters.outbound.mcp.mcp_zoho_chat_platform_adapter import McpZohoChatPlatformAdapter


class FakeMcpClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return {"sent": True}


async def test_send_progress_update_calls_mcp_tool_with_tenant_id():
    fake_client = FakeMcpClient()
    adapter = McpZohoChatPlatformAdapter(mcp_client=fake_client, tenant_id="agb")

    await adapter.send_progress_update("req-1")

    assert fake_client.calls == [("send_progress_update", {"tenant_id": "agb", "request_id": "req-1"})]


async def test_send_final_response_calls_mcp_tool_with_answer_text():
    fake_client = FakeMcpClient()
    adapter = McpZohoChatPlatformAdapter(mcp_client=fake_client, tenant_id="agb")

    await adapter.send_final_response("req-1", "la respuesta")

    assert fake_client.calls == [
        ("send_final_response", {"tenant_id": "agb", "request_id": "req-1", "answer_text": "la respuesta"})
    ]
