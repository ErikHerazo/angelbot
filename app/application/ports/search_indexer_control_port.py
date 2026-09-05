from typing import Optional, Protocol


class SearchIndexerControlPort(Protocol):
    """Direct control of the Azure AI Search indexer itself -- distinct
    from SearchIndexerTriggerPort, which just enqueues the Celery job that
    ends up calling this."""

    async def get_last_result_status(self) -> Optional[str]: ...

    async def start(self) -> None: ...
