import asyncio
import os

import yaml

from app.application.ports.search_indexer_config_repository_port import SearchIndexerConfig


class FilesystemSearchIndexerConfigRepository:
    """Implements SearchIndexerConfigRepositoryPort, reading
    search_indexer.yaml from config/tenants/{tenant_id}/."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_config(self, tenant_id: str) -> SearchIndexerConfig:
        return await asyncio.to_thread(self._read_config, tenant_id)

    def _read_config(self, tenant_id: str) -> SearchIndexerConfig:
        path = os.path.join(self._config_dir, tenant_id, "search_indexer.yaml")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return SearchIndexerConfig(**data)
