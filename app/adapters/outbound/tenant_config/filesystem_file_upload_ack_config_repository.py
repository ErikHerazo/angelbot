import asyncio
import os


class FilesystemFileUploadAckConfigRepository:
    """Implements FileUploadAckConfigRepositoryPort, reading
    file_upload_ack_message.txt from config/tenants/{tenant_id}/ -- plain
    text, same reasoning as greeting.txt/continue_message.txt."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_message(self, tenant_id: str) -> str:
        return await asyncio.to_thread(self._read_message, tenant_id)

    def _read_message(self, tenant_id: str) -> str:
        path = os.path.join(self._config_dir, tenant_id, "file_upload_ack_message.txt")

        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
