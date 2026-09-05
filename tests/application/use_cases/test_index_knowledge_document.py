from app.application.use_cases.index_knowledge_document import IndexKnowledgeDocument


class FakeSearchIndexerControl:
    def __init__(self, last_status):
        self._last_status = last_status
        self.started = False

    async def get_last_result_status(self):
        return self._last_status

    async def start(self):
        self.started = True


async def test_starts_indexer_when_not_already_running():
    control = FakeSearchIndexerControl(last_status="success")
    use_case = IndexKnowledgeDocument(search_indexer=control)

    result = await use_case.execute()

    assert result.status == "started"
    assert control.started is True


async def test_does_not_start_indexer_when_already_running():
    control = FakeSearchIndexerControl(last_status="inProgress")
    use_case = IndexKnowledgeDocument(search_indexer=control)

    result = await use_case.execute()

    assert result.status == "already_running"
    assert control.started is False
