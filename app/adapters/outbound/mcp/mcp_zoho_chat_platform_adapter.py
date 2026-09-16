from app.adapters.outbound.mcp.mcp_http_client import McpHttpClient


class McpZohoChatPlatformAdapter:
    """Implements ChatPlatformPort via clinyq-mcp-zoho, instead of calling
    Zoho SalesIQ's REST API directly (see ZohoChatPlatformAdapter).

    `tenant_id` is bound at construction, same treatment as every other
    tenant-bound outbound adapter -- clinyq-mcp-zoho's tools take it as an
    explicit argument and resolve that tenant's own server_uri/screenname/
    access_token internally, so this adapter never handles Zoho credentials
    itself.
    """

    def __init__(self, *, mcp_client: McpHttpClient, tenant_id: str):
        self._client = mcp_client
        self._tenant_id = tenant_id

    async def send_progress_update(self, request_id: str) -> None:
        await self._client.call_tool(
            "send_progress_update", {"tenant_id": self._tenant_id, "request_id": request_id}
        )

    async def send_final_response(self, request_id: str, answer_text: str) -> None:
        await self._client.call_tool(
            "send_final_response",
            {"tenant_id": self._tenant_id, "request_id": request_id, "answer_text": answer_text},
        )
