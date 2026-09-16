from typing import Protocol


class AdvisorAvailableReplyConfigRepositoryPort(Protocol):
    async def get_reply(self, tenant_id: str) -> str: ...
