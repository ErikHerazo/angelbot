"""Builds the shared ClinyqMCP server instance -- and does nothing else.

This file knows nothing about Azure Search, Zoho, or any other external
service. Each service's own tools module (e.g. `azure_search/tools.py`)
imports `mcp` from here and registers its tools onto it via `@mcp.tool`.

ClinyqMCP is ClinyQ's own multi-tenant MCP server -- AGB is one tenant among
however many clients end up using it, not the owner of this file. Every
tool registered anywhere in this tree takes an explicit `tenant_id` and
resolves that tenant's own config (endpoint, index, credentials) via the
app's existing hexagonal config repos + SecretsPort -- see each tools.py
module for specifics.
"""

from fastmcp import FastMCP

mcp = FastMCP(name="ClinyqMCP")
