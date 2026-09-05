from dataclasses import dataclass
from typing import Protocol


@dataclass
class PriceCatalogConfig:
    search_endpoint: str
    index_name: str


class PriceCatalogConfigRepositoryPort(Protocol):
    async def get_config(self, tenant_id: str) -> PriceCatalogConfig: ...
