from app.adapters.outbound.tenant_config.tenant_config_file import read_tenant_config_block
from app.application.ports.zoho_config_repository_port import ZohoConnectionConfig


class FilesystemZohoConfigRepository:
    """Implements ZohoConfigRepositoryPort, reading the "zoho" block from
    config/tenants/{tenant_id}/config.yaml."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_config(self, tenant_id: str) -> ZohoConnectionConfig:
        data = await read_tenant_config_block(self._config_dir, tenant_id, "zoho")
        return ZohoConnectionConfig(**data)
