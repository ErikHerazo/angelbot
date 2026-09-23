from typing import Protocol


class MinorPatientDeferralConfigRepositoryPort(Protocol):
    async def get_reply(self, tenant_id: str) -> str: ...
