import asyncio
from typing import Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexerClient


class AzureSearchIndexerControlAdapter:
    """Implements SearchIndexerControlPort against Azure AI Search.

    Sync SDK (azure-search-documents), same reasoning as
    AzureBlobStorageAdapter: the async variant needs `aiohttp` (not a
    dependency, confirmed unavailable), so this wraps the sync client in
    `asyncio.to_thread` instead of adding it.
    """

    def __init__(self, *, endpoint: str, api_key: str, indexer_name: str):
        self._indexer_name = indexer_name
        self._client = SearchIndexerClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))

    async def get_last_result_status(self) -> Optional[str]:
        return await asyncio.to_thread(self._get_last_result_status)

    def _get_last_result_status(self) -> Optional[str]:
        status = self._client.get_indexer_status(self._indexer_name)
        return str(status.last_result.status) if status.last_result else None

    async def start(self) -> None:
        await asyncio.to_thread(self._client.run_indexer, self._indexer_name)
