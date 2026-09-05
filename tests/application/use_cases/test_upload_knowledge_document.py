import pytest

from app.application.use_cases.upload_knowledge_document import UploadKnowledgeDocument
from app.domain.value_objects.knowledge_document import InvalidDocumentUploadError


class FakeBlobStorage:
    def __init__(self, containers):
        self._containers = containers
        self.uploads = []

    async def list_containers(self):
        return self._containers

    async def upload(self, *, container_name, blob_name, content, metadata):
        self.uploads.append((container_name, blob_name, content, metadata))


class FakeSearchIndexer:
    def __init__(self, task_id="task-123"):
        self._task_id = task_id
        self.triggered = False

    def trigger(self):
        self.triggered = True
        return self._task_id


async def test_uploads_and_triggers_indexer_on_success():
    blob_storage = FakeBlobStorage(["price-lists"])
    search_indexer = FakeSearchIndexer(task_id="task-abc")
    use_case = UploadKnowledgeDocument(
        blob_storage=blob_storage,
        search_indexer=search_indexer,
        allowed_extensions={".pdf"},
        allowed_mime_types={"application/pdf"},
        max_size_bytes=10 * 1024 * 1024,
    )

    result = await use_case.execute(
        container_name="price-lists",
        filename="precios 2026.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        content=b"fake-bytes",
        metadata={"source": "admin"},
    )

    assert result.blob_name == "precios_2026.pdf"
    assert result.task_id == "task-abc"
    assert blob_storage.uploads == [("price-lists", "precios_2026.pdf", b"fake-bytes", {"source": "admin"})]
    assert search_indexer.triggered is True


async def test_rejects_invalid_container_without_uploading():
    blob_storage = FakeBlobStorage(["price-lists"])
    search_indexer = FakeSearchIndexer()
    use_case = UploadKnowledgeDocument(
        blob_storage=blob_storage,
        search_indexer=search_indexer,
        allowed_extensions={".pdf"},
        allowed_mime_types={"application/pdf"},
        max_size_bytes=10 * 1024 * 1024,
    )

    with pytest.raises(InvalidDocumentUploadError):
        await use_case.execute(
            container_name="not-allowed",
            filename="precios.pdf",
            content_type="application/pdf",
            size_bytes=2048,
            content=b"x",
            metadata={},
        )

    assert blob_storage.uploads == []
    assert search_indexer.triggered is False


async def test_rejects_invalid_file_before_checking_container():
    blob_storage = FakeBlobStorage(["price-lists"])
    search_indexer = FakeSearchIndexer()
    use_case = UploadKnowledgeDocument(
        blob_storage=blob_storage,
        search_indexer=search_indexer,
        allowed_extensions={".pdf"},
        allowed_mime_types={"application/pdf"},
        max_size_bytes=10 * 1024 * 1024,
    )

    with pytest.raises(InvalidDocumentUploadError):
        await use_case.execute(
            container_name="price-lists",
            filename="malware.exe",
            content_type="application/octet-stream",
            size_bytes=2048,
            content=b"x",
            metadata={},
        )

    assert search_indexer.triggered is False
