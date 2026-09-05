from dataclasses import dataclass

from app.application.ports.search_indexer_control_port import SearchIndexerControlPort
from app.domain.value_objects.search_indexer import should_start_indexer


@dataclass
class IndexKnowledgeDocumentResult:
    status: str  # "started" | "already_running"


class IndexKnowledgeDocument:
    def __init__(self, *, search_indexer: SearchIndexerControlPort):
        self._search_indexer = search_indexer

    async def execute(self) -> IndexKnowledgeDocumentResult:
        last_status = await self._search_indexer.get_last_result_status()

        if not should_start_indexer(last_status):
            return IndexKnowledgeDocumentResult(status="already_running")

        await self._search_indexer.start()

        return IndexKnowledgeDocumentResult(status="started")
