from typing import Protocol


class PectusPolandDisambiguationConfigRepositoryPort(Protocol):
    async def get_reply(self, tenant_id: str) -> str: ...
