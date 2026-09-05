import asyncio
import os


class FilesystemGreetingConfigRepository:
    """Implements GreetingConfigRepositoryPort, reading greeting.txt from
    config/tenants/{tenant_id}/ -- plain text, not YAML, since it's a single
    block of business copy with no structure (same reasoning as the
    DISAMBIGUATION_RULES/MINOR_SAFETY_RULE source .txt files)."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_greeting(self, tenant_id: str) -> str:
        return await asyncio.to_thread(self._read_greeting, tenant_id)

    def _read_greeting(self, tenant_id: str) -> str:
        path = os.path.join(self._config_dir, tenant_id, "greeting.txt")

        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
