from typing import Protocol


class FlowConfirmationReplyConfigRepositoryPort(Protocol):
    async def get_reply(self, tenant_id: str) -> str: ...
