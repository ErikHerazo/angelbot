from app.domain.value_objects.search_indexer import should_start_indexer


def test_starts_when_no_previous_run():
    assert should_start_indexer(None) is True


def test_starts_when_last_run_succeeded():
    assert should_start_indexer("success") is True


def test_does_not_start_when_already_in_progress():
    assert should_start_indexer("inProgress") is False
