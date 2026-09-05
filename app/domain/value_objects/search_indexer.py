from typing import Optional


def should_start_indexer(last_result_status: Optional[str]) -> bool:
    """Pure rule: don't start a new indexer run while the last one is still
    in progress."""
    return last_result_status != "inProgress"
