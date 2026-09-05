import asyncio
import os

import yaml

from app.application.ports.zoho_config_repository_port import ZohoConnectionConfig


class FilesystemZohoConfigRepository:
    """Implements ZohoConfigRepositoryPort, reading zoho.yaml from config/tenants/{tenant_id}/."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_config(self, tenant_id: str) -> ZohoConnectionConfig:
        return await asyncio.to_thread(self._read_config, tenant_id)

    def _read_config(self, tenant_id: str) -> ZohoConnectionConfig:
        path = os.path.join(self._config_dir, tenant_id, "zoho.yaml")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return ZohoConnectionConfig(**data)
