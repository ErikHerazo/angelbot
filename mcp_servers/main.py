"""The only file that knows every service registered on ClinyqMCP.

`clinyq_mcp.py` builds the bare server; each `{service}/tools.py` module
registers its own tools onto it as a side effect of being imported. This
file is what actually imports all of them together and exposes the final
`mcp` object -- this is what `fastmcp run` (see fastmcp.json's
`source.path`) points at.

Organized by client company (Erik's call, 2026-09-15): we don't know yet
what tools future clients will need, or whether their versions of a
same-sounding capability (e.g. a price-catalog search) will share the same
Azure Search field names AGB's does -- so tools live under `{empresa}/`,
not under a shared `{service}/`, and if a second company ever needs
something name-identical to one of AGB's tools, it gets renamed then (e.g.
`agb_search_price_catalog`), not designed around speculatively now.

Adding a new client's tools means adding one import line here -- nothing
else in this file changes.
"""

from clinyq_mcp import mcp

# Each import below registers that client's tools onto `mcp` as a side
# effect (the `@mcp.tool` decorators run at import time) -- the local name
# is never referenced afterward, that's expected, not a mistake.
from agb.azure_search import tools as agb_azure_search_tools  # noqa: F401
from agb.zoho import tools as agb_zoho_tools  # noqa: F401
from agb.azure_blob import tools as agb_azure_blob_tools  # noqa: F401
from azure_translator import tools as azure_translator_tools  # noqa: F401  # shared ClinyQ infra, not under agb/

__all__ = ["mcp"]


if __name__ == "__main__":
    # Manual sanity-check script (`python main.py`), same convention as this
    # repo's other `test_*.py` standalone scripts -- lists whatever the
    # server actually exposes right now (tools/list, resources/list,
    # prompts/list) via a real in-process MCP client, no HTTP server needed.
    # Not what runs in prod -- see fastmcp.json/Dockerfile for that
    # (`fastmcp run fastmcp.json`).
    import asyncio

    from fastmcp import Client

    async def _print_server_capabilities() -> None:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            print(f"Tools ({len(tools)}):")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")

            resources = await client.list_resources()
            print(f"Resources ({len(resources)}):")
            for resource in resources:
                print(f"  - {resource.uri}")

            prompts = await client.list_prompts()
            print(f"Prompts ({len(prompts)}):")
            for prompt in prompts:
                print(f"  - {prompt.name}")

    asyncio.run(_print_server_capabilities())
