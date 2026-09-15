"""Registers Azure Blob Storage tools onto the shared ClinyqMCP server.

Multi-tenant, generic code: each tool takes an explicit `tenant_id` and
resolves that tenant's own Blob Storage connection string via the
`azure-blob-connection-string-{tenant_id}` secret, same SecretsPort used by
`AzureBlobStorageAdapter` in the main FastAPI app. No separate YAML config
file needed here (unlike azure_search/zoho) -- a connection string already
carries the account, there's no separate endpoint/index-name to declare.

Ported from `app/adapters/outbound/azure_blob/azure_blob_storage_adapter.py`.
Uses the synchronous `azure-storage-blob` SDK wrapped in `asyncio.to_thread`
(same reasoning as that adapter: the async variant needs `aiohttp`, not a
dependency here either) -- this is the one MCP so far that needs a real
Azure SDK instead of a plain `httpx` REST call, so `azure-storage-blob` is
in this tree's requirements.txt specifically for this module.

`upload_document`'s `content_base64` param exists because MCP tool
arguments are JSON over the wire -- raw bytes can't cross that boundary
directly, so binary content is base64-encoded by the caller and decoded
here before handing it to the SDK.

Lives under `agb/` for the same reason `azure_search`/`zoho` do: this is a
per-tenant resource (each client has their own Storage account), and we
don't know yet what a second client's needs look like here.
"""

import asyncio
import base64
import os
import sys

from azure.storage.blob import BlobServiceClient

_MCP_SERVERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_MCP_SERVERS_DIR, ".."))
for _path in (_REPO_ROOT, _MCP_SERVERS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(_REPO_ROOT, ".env"))

from app.adapters.outbound.secrets.env_file_secrets_adapter import EnvFileSecretsAdapter
from app.core.utils.normalize_metadata import normalize_blob_metadata

from clinyq_mcp import mcp

_secrets = EnvFileSecretsAdapter()


async def _client_for_tenant(tenant_id: str) -> BlobServiceClient:
    connection_string = await _secrets.get_secret(f"azure-blob-connection-string-{tenant_id}")
    return await asyncio.to_thread(BlobServiceClient.from_connection_string, connection_string)


@mcp.tool
async def list_containers(tenant_id: str) -> list[str]:
    """List the Blob Storage container names available for a tenant."""
    client = await _client_for_tenant(tenant_id)
    return await asyncio.to_thread(lambda: [c.name for c in client.list_containers()])


@mcp.tool
async def upload_document(
    tenant_id: str,
    container_name: str,
    blob_name: str,
    content_base64: str,
    metadata: dict | None = None,
) -> dict:
    """Upload a document (base64-encoded) to a tenant's Blob Storage container.

    Overwrites an existing blob with the same name. `metadata` values are
    normalized (keys lowercased/sanitized, values stringified and truncated
    to 8000 chars) the same way the legacy upload path does.
    """
    client = await _client_for_tenant(tenant_id)
    content = base64.b64decode(content_base64)
    blob_metadata = normalize_blob_metadata(metadata) if metadata else {}

    def _upload():
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.upload_blob(content, overwrite=True, metadata=blob_metadata)

    await asyncio.to_thread(_upload)
    return {"uploaded": True, "container_name": container_name, "blob_name": blob_name}
