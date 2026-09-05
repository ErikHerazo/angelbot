from app.adapters.outbound.tenant_config.filesystem_price_catalog_config_repository import (
    FilesystemPriceCatalogConfigRepository,
)


async def test_reads_agb_price_catalog_config_from_real_config():
    repository = FilesystemPriceCatalogConfigRepository(config_dir="app/config/tenants")

    config = await repository.get_config("agb")

    assert config.search_endpoint == "https://agb-search.search.windows.net"
    assert config.index_name == "rag-structured-data-3-large"
