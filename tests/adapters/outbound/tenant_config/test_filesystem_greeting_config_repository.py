from app.adapters.outbound.tenant_config.filesystem_greeting_config_repository import (
    FilesystemGreetingConfigRepository,
)


async def test_reads_agb_greeting_from_real_config():
    repository = FilesystemGreetingConfigRepository(config_dir="app/config/tenants")

    greeting = await repository.get_greeting("agb")

    assert "Aesthea" in greeting
    assert "Antiaging Group Barcelona" in greeting
