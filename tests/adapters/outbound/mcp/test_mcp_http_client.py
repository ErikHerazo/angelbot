import json

import httpx
import pytest

from app.adapters.outbound.mcp.mcp_http_client import McpHttpClient, McpToolError


def _sse_response(payload: dict) -> httpx.Response:
    body = f"event: message\ndata: {json.dumps(payload)}\n\n"
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        text=body,
    )


def _client_with(handler) -> McpHttpClient:
    return McpHttpClient(base_url="http://fake-mcp/mcp", transport=httpx.MockTransport(handler))


async def test_list_tools_parses_sse_response():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "tools/list"
        assert request.headers["accept"] == "application/json, text/event-stream"
        return _sse_response(
            {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"tools": [{"name": "search_price_catalog", "inputSchema": {}}]},
            }
        )

    client = _client_with(handler)
    tools = await client.list_tools()

    assert tools == [{"name": "search_price_catalog", "inputSchema": {}}]


async def test_call_tool_returns_structured_content():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["params"] == {"name": "search_price_catalog", "arguments": {"tenant_id": "agb", "query": "nariz"}}
        return _sse_response(
            {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "isError": False,
                    "content": [{"type": "text", "text": "[]"}],
                    "structuredContent": {"result": [{"procedure_name": "RINOPLASTIA"}]},
                },
            }
        )

    client = _client_with(handler)
    result = await client.call_tool("search_price_catalog", {"tenant_id": "agb", "query": "nariz"})

    assert result == [{"procedure_name": "RINOPLASTIA"}]


async def test_call_tool_falls_back_to_text_content_without_structured_content():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return _sse_response(
            {"jsonrpc": "2.0", "id": body["id"], "result": {"isError": False, "content": [{"type": "text", "text": "hola"}]}}
        )

    client = _client_with(handler)
    result = await client.call_tool("some_tool", {})

    assert result == "hola"


async def test_call_tool_raises_on_is_error():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return _sse_response(
            {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"isError": True, "content": [{"type": "text", "text": "boom"}]},
            }
        )

    client = _client_with(handler)

    with pytest.raises(McpToolError, match="boom"):
        await client.call_tool("some_tool", {})


async def test_transport_error_raises_mcp_tool_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = _client_with(handler)

    with pytest.raises(McpToolError):
        await client.list_tools()
