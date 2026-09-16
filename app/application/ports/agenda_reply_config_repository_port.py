from typing import Protocol


class AgendaReplyConfigRepositoryPort(Protocol):
    async def get_reply(self, tenant_id: str) -> str: ...
