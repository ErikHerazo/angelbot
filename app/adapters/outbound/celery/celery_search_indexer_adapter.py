from typing import Callable, Optional


class CelerySearchIndexerAdapter:
    """Implements SearchIndexerTriggerPort, wrapping run_search_indexer.delay().

    `trigger_fn` is injected (defaults lazily to the real Celery task) so
    this adapter is importable/testable without app.tasks.celery's import
    chain, which requires AZURE_CLIENT_ID/AZURE_TENANT_ID/CELERY_BROKER_URL
    etc. to be set (same local-env limitation as azure_openai.py's pyodbc
    chain, different root cause).
    """

    def __init__(self, *, trigger_fn: Optional[Callable] = None):
        if trigger_fn is None:
            from app.tasks.tasks import run_search_indexer

            trigger_fn = run_search_indexer.delay

        self._trigger_fn = trigger_fn

    def trigger(self) -> str:
        task = self._trigger_fn()
        return task.id
