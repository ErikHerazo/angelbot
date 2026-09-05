from typing import Protocol

from app.domain.entities.tenant import Tenant


class TenantRepositoryPort(Protocol):
    async def get_tenant(self, tenant_id: str) -> Tenant: ...
