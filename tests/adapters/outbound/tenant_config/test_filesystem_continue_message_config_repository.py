from app.adapters.outbound.tenant_config.filesystem_continue_message_config_repository import (
    FilesystemContinueMessageConfigRepository,
)


async def test_reads_agb_continue_message_from_real_config():
    repository = FilesystemContinueMessageConfigRepository(config_dir="app/config/tenants")

    message = await repository.get_message("agb")

    assert "sigo contigo" in message
