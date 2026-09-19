import itertools
import json
from typing import Any, Optional

import httpx


class McpToolError(Exception):
    """Raised when an MCP tool call returns isError=true, or the transport fails."""


class McpHttpClient:
    """Minimal MCP Streamable HTTP JSON-RPC client for stateless FastMCP servers.

    Hand-rolled on httpx instead of the official `mcp`/`fastmcp` client packages --
    both pull in dependency chains (starlette>=1.0 for fastmcp, PyJWT>=2.10 for mcp,
    which then forces redis-entraid>=1.2 -> azure-identity>=1.24) that conflict with
    this repo's pinned versions, same class of conflict already documented for fastmcp
    in CLAUDE.md. Confirmed via a real running clinyq-mcp-azure-search container that
    stateless mode needs no `initialize` handshake -- a single POST per call is enough,
    and the server always replies as a one-shot SSE event (`text/event-stream`), never
    plain `application/json`, even though the spec allows either -- the client must
    still send both media types in `Accept` or the server responds 406.
    """

    def __init__(
        self,
        *,
        base_url: str,
        auth_token: Optional[str] = None,
        timeout: float = 15.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._url = base_url.rstrip("/")
        self._auth_token = auth_token
        self._timeout = timeout
        self._transport = transport
        self._ids = itertools.count(1)

    async def _request(self, method: str, params: Optional[dict] = None) -> dict:
        payload: dict = {"jsonrpc": "2.0", "id": next(self._ids), "method": method}
        if params is not None:
            payload["params"] = params

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise McpToolError(f"MCP transport error calling '{method}' on {self._url}: {e}")

        return self._parse_body(response)

    @staticmethod
    def _parse_body(response: httpx.Response) -> dict:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[len("data:"):].strip())
            raise McpToolError(f"No data event in SSE response: {response.text!r}")
        return response.json()

    async def list_tools(self) -> list[dict]:
        body = await self._request("tools/list")
        if "error" in body:
            raise McpToolError(f"tools/list error: {body['error']}")
        return body["result"]["tools"]

    async def call_tool(self, name: str, arguments: dict) -> Any:
        body = await self._request("tools/call", {"name": name, "arguments": arguments})
        if "error" in body:
            raise McpToolError(f"{name}: {body['error']}")

        result = body["result"]
        if result.get("isError"):
            text = result["content"][0]["text"] if result.get("content") else "unknown MCP tool error"
            raise McpToolError(f"{name}: {text}")

        structured = result.get("structuredContent")
        if structured is not None and "result" in structured:
            return structured["result"]
        if result.get("content"):
            return result["content"][0].get("text")
        return None
