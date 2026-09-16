from app.adapters.outbound.tenant_config.tenant_config_file import read_tenant_config_block
from app.application.ports.knowledge_base_config_repository_port import KnowledgeBaseConfig


class FilesystemKnowledgeBaseConfigRepository:
    """Implements KnowledgeBaseConfigRepositoryPort, reading the
    "knowledge_base" block from config/tenants/{tenant_id}/config.yaml --
    same pattern as FilesystemPriceCatalogConfigRepository, kept as its own
    block since it's a separate index (main knowledge base vs. price
    catalog) even though both live on the same Azure Search service today."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_config(self, tenant_id: str) -> KnowledgeBaseConfig:
        data = await read_tenant_config_block(self._config_dir, tenant_id, "knowledge_base")
        return KnowledgeBaseConfig(**data)
