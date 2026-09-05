from dataclasses import dataclass
from typing import Protocol


@dataclass
class SearchIndexerConfig:
    search_endpoint: str
    indexer_name: str


class SearchIndexerConfigRepositoryPort(Protocol):
    async def get_config(self, tenant_id: str) -> SearchIndexerConfig: ...
