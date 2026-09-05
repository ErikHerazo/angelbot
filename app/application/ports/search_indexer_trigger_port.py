from typing import Protocol


class SearchIndexerTriggerPort(Protocol):
    def trigger(self) -> str:
        """Enqueues the indexer job and returns its task id."""
        ...
