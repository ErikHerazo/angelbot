import asyncio
import os

import yaml

from app.application.ports.price_catalog_config_repository_port import PriceCatalogConfig


class FilesystemPriceCatalogConfigRepository:
    """Implements PriceCatalogConfigRepositoryPort, reading price_catalog.yaml
    from config/tenants/{tenant_id}/."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_config(self, tenant_id: str) -> PriceCatalogConfig:
        return await asyncio.to_thread(self._read_config, tenant_id)

    def _read_config(self, tenant_id: str) -> PriceCatalogConfig:
        path = os.path.join(self._config_dir, tenant_id, "price_catalog.yaml")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return PriceCatalogConfig(**data)
