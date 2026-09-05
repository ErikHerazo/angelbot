import asyncio
import os

import yaml

from app.domain.entities.tenant import Tenant


class FilesystemTenantRepository:
    """Implements TenantRepositoryPort, reading tenant.yaml from config/tenants/{tenant_id}/."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_tenant(self, tenant_id: str) -> Tenant:
        return await asyncio.to_thread(self._read_tenant, tenant_id)

    def _read_tenant(self, tenant_id: str) -> Tenant:
        path = os.path.join(self._config_dir, tenant_id, "tenant.yaml")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return Tenant(**data)
