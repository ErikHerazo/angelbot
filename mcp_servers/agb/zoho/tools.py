"""Registers Zoho SalesIQ callback tools onto the shared ClinyqMCP server.

This module owns no server instance of its own -- it imports `mcp` from
`clinyq_mcp.py` and attaches its tools to it. Importing this module is
itself what registers the tools (the `@mcp.tool` decorators run at import
time); see `main.py` for where that import actually happens.

Multi-tenant, generic code: each tool takes an explicit `tenant_id` and
resolves that tenant's own Zoho server_uri/screenname (config/tenants/
{tenant_id}/zoho.yaml) and access token (the `zoho-access-token-{tenant_id}`
secret) via the same hexagonal config repo + SecretsPort already used by
`ZohoChatPlatformAdapter` in the main FastAPI app.

Ported from `app/adapters/outbound/zoho/zoho_chat_platform_adapter.py`
(itself ported from the legacy `app/services/zoho/client.py::ZohoClient`).
Deliberately does NOT reraise as `fastapi.HTTPException` like that adapter
does -- there's no FastAPI request context here to bubble an HTTP error
to, so a plain `response.raise_for_status()` is enough; the calling agent
sees the httpx exception directly.

Lives under `agb/` for the same reason `azure_search` does (see that
module and main.py's docstring): we don't know yet whether future clients
will even use Zoho, so this isn't designed as a generic "any chat platform"
tool -- if a second client needs the same shape, it gets its own
`{empresa}/zoho/tools.py` (or a renamed tool if it collides) then, not a
speculative abstraction now.
"""

import os
import sys

import httpx

_MCP_SERVERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_MCP_SERVERS_DIR, ".."))
for _path in (_REPO_ROOT, _MCP_SERVERS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(_REPO_ROOT, ".env"))

from app.adapters.outbound.secrets.env_file_secrets_adapter import EnvFileSecretsAdapter
from app.adapters.outbound.tenant_config.filesystem_zoho_config_repository import (
    FilesystemZohoConfigRepository,
)

from clinyq_mcp import mcp

CONFIG_DIR = os.path.join(_REPO_ROOT, "app", "config", "tenants")

_zoho_config = FilesystemZohoConfigRepository(CONFIG_DIR)
_secrets = EnvFileSecretsAdapter()


async def _post(access_token: str, url: str, payload: dict, timeout: float = 10.0) -> None:
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()


@mcp.tool
async def send_progress_update(tenant_id: str, request_id: str) -> dict:
    """Send a 'progress' ping to Zoho SalesIQ, extending its webhook timeout
    while the real answer is still being generated for `request_id`."""
    config = await _zoho_config.get_config(tenant_id)
    access_token = await _secrets.get_secret(f"zoho-access-token-{tenant_id}")

    url = f"https://{config.server_uri}/api/v2/{config.screenname}/callbacks/{request_id}/progress"
    await _post(access_token, url, {"text": "Just a few more seconds.."})
    return {"sent": True}


@mcp.tool
async def send_final_response(tenant_id: str, request_id: str, answer_text: str) -> dict:
    """Send the final generated answer back to Zoho SalesIQ, completing the
    pending callback for `request_id`."""
    config = await _zoho_config.get_config(tenant_id)
    access_token = await _secrets.get_secret(f"zoho-access-token-{tenant_id}")

    url = f"https://{config.server_uri}/api/v2/{config.screenname}/callbacks/{request_id}/response"
    payload = {"action": "reply", "replies": [{"text": answer_text}]}
    await _post(access_token, url, payload, timeout=30.0)
    return {"sent": True}
