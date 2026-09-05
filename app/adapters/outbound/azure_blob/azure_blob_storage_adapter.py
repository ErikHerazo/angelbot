import asyncio

from azure.storage.blob import BlobServiceClient

from app.core.utils.normalize_metadata import normalize_blob_metadata


class AzureBlobStorageAdapter:
    """Implements BlobStoragePort against Azure Blob Storage.

    Uses the synchronous azure-storage-blob SDK (the async variant needs
    `aiohttp`, not currently a dependency, just to fix this one blocking
    call) wrapped in `asyncio.to_thread` -- non-blocking without adding a
    new dependency, same technique already used by the Filesystem*ConfigRepository
    adapters for blocking file I/O.
    """

    def __init__(self, *, connection_string: str):
        self._client = BlobServiceClient.from_connection_string(connection_string)

    async def list_containers(self) -> list[str]:
        return await asyncio.to_thread(self._list_containers)

    def _list_containers(self) -> list[str]:
        return [c.name for c in self._client.list_containers()]

    async def upload(self, *, container_name: str, blob_name: str, content, metadata: dict) -> None:
        await asyncio.to_thread(self._upload, container_name, blob_name, content, metadata)

    def _upload(self, container_name: str, blob_name: str, content, metadata: dict) -> None:
        blob_client = self._client.get_blob_client(container=container_name, blob=blob_name)
        blob_metadata = normalize_blob_metadata(metadata) if metadata else {}
        blob_client.upload_blob(content, overwrite=True, metadata=blob_metadata)
