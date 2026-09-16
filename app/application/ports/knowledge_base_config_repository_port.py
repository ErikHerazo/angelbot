from dataclasses import dataclass
from typing import Protocol


@dataclass
class KnowledgeBaseConfig:
    search_endpoint: str
    index_name: str
    semantic_configuration: str


class KnowledgeBaseConfigRepositoryPort(Protocol):
    async def get_config(self, tenant_id: str) -> KnowledgeBaseConfig: ...
