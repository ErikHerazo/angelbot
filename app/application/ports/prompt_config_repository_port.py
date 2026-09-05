from typing import Protocol


class PromptConfigRepositoryPort(Protocol):
    async def get_base_prompt(self, tenant_id: str, channel: str) -> str: ...
