import asyncio
import os


class FilesystemContinueMessageConfigRepository:
    """Implements ContinueMessageConfigRepositoryPort, reading
    continue_message.txt from config/tenants/{tenant_id}/ -- plain text,
    same reasoning as greeting.txt."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_message(self, tenant_id: str) -> str:
        return await asyncio.to_thread(self._read_message, tenant_id)

    def _read_message(self, tenant_id: str) -> str:
        path = os.path.join(self._config_dir, tenant_id, "continue_message.txt")

        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
