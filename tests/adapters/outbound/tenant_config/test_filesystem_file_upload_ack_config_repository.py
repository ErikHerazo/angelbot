from app.adapters.outbound.tenant_config.filesystem_file_upload_ack_config_repository import (
    FilesystemFileUploadAckConfigRepository,
)


async def test_reads_agb_file_upload_ack_message_from_real_config():
    repository = FilesystemFileUploadAckConfigRepository(config_dir="app/config/tenants")

    message = await repository.get_message("agb")

    assert "subido con" in message
