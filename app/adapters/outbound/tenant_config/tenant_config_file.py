import asyncio
import os

import yaml


def _read_config_file(config_dir: str, tenant_id: str) -> dict:
    path = os.path.join(config_dir, tenant_id, "config.yaml")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def read_tenant_config_block(config_dir: str, tenant_id: str, block_key: str) -> dict:
    """Reads config/tenants/{tenant_id}/config.yaml and returns the named
    block (e.g. "tenant", "zoho", "business_hours") -- one shared file per
    tenant with a block per concern, not one file per concern (Erik's call:
    matches the config.yaml convention already used in the clinyq-mcp-*
    repos, applied here too)."""
    data = await asyncio.to_thread(_read_config_file, config_dir, tenant_id)
    return data[block_key]
