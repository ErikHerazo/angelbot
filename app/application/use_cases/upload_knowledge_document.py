from dataclasses import dataclass
from typing import Optional

from app.application.ports.blob_storage_port import BlobStoragePort
from app.application.ports.search_indexer_trigger_port import SearchIndexerTriggerPort
from app.domain.value_objects.knowledge_document import (
    InvalidDocumentUploadError,
    sanitize_blob_name,
    validate_document_upload,
)


@dataclass
class UploadKnowledgeDocumentResult:
    blob_name: str
    task_id: str


class UploadKnowledgeDocument:
    def __init__(
        self,
        *,
        blob_storage: BlobStoragePort,
        search_indexer: SearchIndexerTriggerPort,
        allowed_extensions: set[str],
        allowed_mime_types: set[str],
        max_size_bytes: int,
    ):
        self._blob_storage = blob_storage
        self._search_indexer = search_indexer
        self._allowed_extensions = allowed_extensions
        self._allowed_mime_types = allowed_mime_types
        self._max_size_bytes = max_size_bytes

    async def execute(
        self,
        *,
        container_name: str,
        filename: str,
        content_type: Optional[str],
        size_bytes: int,
        content,
        metadata: dict,
        prefix: Optional[str] = None,
    ) -> UploadKnowledgeDocumentResult:
        validate_document_upload(
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            allowed_extensions=self._allowed_extensions,
            allowed_mime_types=self._allowed_mime_types,
            max_size_bytes=self._max_size_bytes,
        )

        containers = await self._blob_storage.list_containers()
        if container_name not in containers:
            raise InvalidDocumentUploadError(f"Invalid container: {container_name}")

        blob_name = sanitize_blob_name(filename, prefix)

        await self._blob_storage.upload(
            container_name=container_name,
            blob_name=blob_name,
            content=content,
            metadata=metadata,
        )

        task_id = self._search_indexer.trigger()

        return UploadKnowledgeDocumentResult(blob_name=blob_name, task_id=task_id)
