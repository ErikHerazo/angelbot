"""Registers Azure AI Search tools onto the shared ClinyqMCP server.

This module owns no server instance of its own -- it imports `mcp` from
`clinyq_mcp.py` and attaches its tools to it. Importing this module is
itself what registers the tools (the `@mcp.tool` decorators run at import
time); see `main.py` for where that import actually happens.

Multi-tenant, generic code: each tool takes an explicit `tenant_id` and
resolves that tenant's own Azure Search endpoint/index/key via the same
hexagonal config repos and SecretsPort already used by the main FastAPI
app (config/tenants/{tenant_id}/price_catalog.yaml, knowledge_base.yaml,
and the azure-search-api-key-{tenant_id} secret) -- deliberately not
reading bare global env vars, so onboarding a second client means adding
their config/tenants/{new_tenant}/*.yaml + secret, never touching this
file or mixing config with AGB's.

Exposes 2 tools, deliberately kept separate even though both hit the same
Azure Search service for AGB today (Erik's call, 2026-09-14): price-catalog
lookup and main-knowledge-base retrieval. A future tenant could point them
at two different Azure Search services entirely -- nothing here assumes
they're the same resource.

No auth on the MCP server itself yet, and the Azure Search key used per
tenant is whatever's in its secret today (the admin key, not scoped down to
a read-only query key) -- both deliberately deferred by Erik until this is
closer to a prod launch, not forgotten.
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
from app.adapters.outbound.tenant_config.filesystem_knowledge_base_config_repository import (
    FilesystemKnowledgeBaseConfigRepository,
)
from app.adapters.outbound.tenant_config.filesystem_price_catalog_config_repository import (
    FilesystemPriceCatalogConfigRepository,
)

from clinyq_mcp import mcp

CONFIG_DIR = os.path.join(_REPO_ROOT, "app", "config", "tenants")
API_VERSION = "2025-11-01-preview"

_price_catalog_config = FilesystemPriceCatalogConfigRepository(CONFIG_DIR)
_knowledge_base_config = FilesystemKnowledgeBaseConfigRepository(CONFIG_DIR)
_secrets = EnvFileSecretsAdapter()


def _search_url(search_endpoint: str, index_name: str) -> str:
    return f"{search_endpoint}/indexes/{index_name}/docs/search?api-version={API_VERSION}"


@mcp.tool
async def search_price_catalog(tenant_id: str, query: str) -> list[dict]:
    """Search a tenant's procedure price-list index for matching procedures.

    Deliberately no `searchMode` override (Azure default, "any") -- Erik's
    2026-09-09 call, see AzureSearchPriceCatalogAdapter's docstring for the
    "all" vs "any" tradeoff history. Returns raw matches (procedure_name,
    price_range_eur) for the calling agent to reason over -- no ambiguity
    cutoff or result-count limiting here, that's caller-side policy.
    """
    config = await _price_catalog_config.get_config(tenant_id)
    api_key = await _secrets.get_secret(f"azure-search-api-key-{tenant_id}")

    payload = {"search": query, "count": True}
    headers = {"Content-Type": "application/json", "api-key": api_key}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _search_url(config.search_endpoint, config.index_name), headers=headers, json=payload
        )
    response.raise_for_status()
    docs = response.json().get("value", [])
    return [
        {
            "procedure_name": doc.get("procedure_name", ""),
            "price_range_eur": doc.get("price_range_eur", ""),
        }
        for doc in docs
    ]


@mcp.tool
async def search_knowledge_base(tenant_id: str, query: str, top_k: int = 5) -> list[str]:
    """Search a tenant's main knowledge-base index (procedures, policies, etc.).

    Hybrid semantic + vector search (same shape as the manual retrieval
    ClaudeFoundryConversationEngineAdapter does today, since Claude has no
    equivalent to Azure OpenAI's native "on your data" grounding). Returns
    extracted captions where available, falling back to the raw chunk text.
    """
    config = await _knowledge_base_config.get_config(tenant_id)
    api_key = await _secrets.get_secret(f"azure-search-api-key-{tenant_id}")

    payload = {
        "search": query,
        "top": top_k,
        "queryType": "semantic",
        "semanticConfiguration": config.semantic_configuration,
        "captions": "extractive",
        "vectorQueries": [{"kind": "text", "text": query, "fields": "text_vector", "k": top_k}],
    }
    headers = {"Content-Type": "application/json", "api-key": api_key}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _search_url(config.search_endpoint, config.index_name), headers=headers, json=payload
        )
    response.raise_for_status()
    docs = response.json().get("value", [])

    chunks = []
    for doc in docs:
        captions = doc.get("@search.captions", [])
        if captions:
            chunks.extend(c["text"] for c in captions if c.get("text"))
        elif doc.get("chunk"):
            chunks.append(doc["chunk"])
    return chunks
