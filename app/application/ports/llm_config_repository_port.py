from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMConfig:
    endpoint: str
    api_version: str
    deployment_primary: str
    deployment_secondary: str
    temperature: float
    max_tokens: int


class LLMConfigRepositoryPort(Protocol):
    async def get_config(self, tenant_id: str) -> LLMConfig: ...
