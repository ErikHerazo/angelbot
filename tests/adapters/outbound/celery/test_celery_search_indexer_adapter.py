from app.adapters.outbound.celery.celery_search_indexer_adapter import CelerySearchIndexerAdapter


class FakeTask:
    def __init__(self, task_id):
        self.id = task_id


def test_trigger_delegates_and_returns_task_id():
    calls = []

    def fake_trigger_fn():
        calls.append(True)
        return FakeTask("task-xyz")

    adapter = CelerySearchIndexerAdapter(trigger_fn=fake_trigger_fn)

    result = adapter.trigger()

    assert result == "task-xyz"
    assert calls == [True]
