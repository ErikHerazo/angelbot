from typing import Protocol


class FileUploadAckConfigRepositoryPort(Protocol):
    async def get_message(self, tenant_id: str) -> str: ...
