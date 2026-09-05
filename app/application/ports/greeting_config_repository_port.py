from typing import Protocol


class GreetingConfigRepositoryPort(Protocol):
    async def get_greeting(self, tenant_id: str) -> str: ...
