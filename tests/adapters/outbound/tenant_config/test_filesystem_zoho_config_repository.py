import pytest

from app.adapters.outbound.tenant_config.filesystem_zoho_config_repository import (
    FilesystemZohoConfigRepository,
)


async def test_reads_agb_zoho_config_from_real_config():
    repository = FilesystemZohoConfigRepository(config_dir="app/config/tenants")

    config = await repository.get_config("agb")

    assert config.server_uri == "salesiq.zoho.eu"
    assert config.screenname == "antiaginggroup"


async def test_raises_when_zoho_config_missing(tmp_path):
    repository = FilesystemZohoConfigRepository(config_dir=str(tmp_path))

    with pytest.raises(FileNotFoundError):
        await repository.get_config("does-not-exist")
