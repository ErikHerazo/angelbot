from app.adapters.outbound.tenant_config.filesystem_search_indexer_config_repository import (
    FilesystemSearchIndexerConfigRepository,
)


async def test_reads_agb_search_indexer_config_from_real_config():
    repository = FilesystemSearchIndexerConfigRepository(config_dir="app/config/tenants")

    config = await repository.get_config("agb")

    assert config.search_endpoint == "https://agb-search.search.windows.net"
    assert config.indexer_name == "rag-updated-agb-container-indexer"
