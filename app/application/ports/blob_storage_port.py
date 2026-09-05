from typing import Protocol


class BlobStoragePort(Protocol):
    async def list_containers(self) -> list[str]: ...

    async def upload(self, *, container_name: str, blob_name: str, content, metadata: dict) -> None: ...
