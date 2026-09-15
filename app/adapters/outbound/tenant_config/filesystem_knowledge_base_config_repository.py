import asyncio
import os

import yaml

from app.application.ports.knowledge_base_config_repository_port import KnowledgeBaseConfig


class FilesystemKnowledgeBaseConfigRepository:
    """Implements KnowledgeBaseConfigRepositoryPort, reading knowledge_base.yaml
    from config/tenants/{tenant_id}/ -- same pattern as
    FilesystemPriceCatalogConfigRepository, kept in its own file/YAML since
    it's a separate index (main knowledge base vs. price catalog) even
    though both live on the same Azure Search service today."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_config(self, tenant_id: str) -> KnowledgeBaseConfig:
        return await asyncio.to_thread(self._read_config, tenant_id)

    def _read_config(self, tenant_id: str) -> KnowledgeBaseConfig:
        path = os.path.join(self._config_dir, tenant_id, "knowledge_base.yaml")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return KnowledgeBaseConfig(**data)
