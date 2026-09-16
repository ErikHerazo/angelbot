from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ClaudeLLMConfig:
    endpoint: str
    deployment: str
    max_tokens: int


class ClaudeLLMConfigRepositoryPort(Protocol):
    async def get_config(self, tenant_id: str) -> ClaudeLLMConfig: ...
