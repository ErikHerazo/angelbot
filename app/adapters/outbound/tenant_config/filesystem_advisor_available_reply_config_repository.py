import asyncio
import os


class FilesystemAdvisorAvailableReplyConfigRepository:
    """Implements AdvisorAvailableReplyConfigRepositoryPort, reading
    advisor_available_reply.txt from config/tenants/{tenant_id}/ -- same
    plain-text, one-concern-per-file pattern as greeting.txt/continue_message.txt."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_reply(self, tenant_id: str) -> str:
        return await asyncio.to_thread(self._read_reply, tenant_id)

    def _read_reply(self, tenant_id: str) -> str:
        path = os.path.join(self._config_dir, tenant_id, "advisor_available_reply.txt")

        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
