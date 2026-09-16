from app.adapters.outbound.tenant_config.tenant_config_file import read_tenant_config_block
from app.domain.entities.tenant import Tenant


class FilesystemTenantRepository:
    """Implements TenantRepositoryPort, reading the "tenant" block from
    config/tenants/{tenant_id}/config.yaml."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_tenant(self, tenant_id: str) -> Tenant:
        data = await read_tenant_config_block(self._config_dir, tenant_id, "tenant")
        return Tenant(**data)
