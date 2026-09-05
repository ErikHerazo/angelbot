from typing import Protocol


class ContinueMessageConfigRepositoryPort(Protocol):
    async def get_message(self, tenant_id: str) -> str: ...
