from app.adapters.outbound.language.reply_language_resolver_adapter import (
    ReplyLanguageResolverAdapter,
)


class FakeConversationHistory:
    def __init__(self, history):
        self._history = history
        self.calls = []

    async def get_history(self, tenant_id, session_id):
        self.calls.append((tenant_id, session_id))
        return self._history

    async def append_turn(self, **kwargs):
        pass


async def test_fetches_history_and_passes_it_to_resolve_fn_when_use_history_true():
    history = [{"role": "user", "content": "hola"}]
    conversation_history = FakeConversationHistory(history)
    captured = {}

    async def fake_resolve_fn(**kwargs):
        captured.update(kwargs)
        return "es"

    adapter = ReplyLanguageResolverAdapter(
        conversation_history=conversation_history,
        resolve_fn=fake_resolve_fn,
    )

    result = await adapter.resolve(tenant_id="agb", session_id="sess-1", language_hint="es")

    assert result == "es"
    assert conversation_history.calls == [("agb", "sess-1")]
    assert captured["history"] == history


async def test_skips_history_fetch_when_use_history_false():
    conversation_history = FakeConversationHistory(history=[{"role": "user", "content": "x"}])
    captured = {}

    async def fake_resolve_fn(**kwargs):
        captured.update(kwargs)
        return "en"

    adapter = ReplyLanguageResolverAdapter(
        conversation_history=conversation_history,
        resolve_fn=fake_resolve_fn,
    )

    await adapter.resolve(tenant_id="agb", session_id="sess-1", use_history=False)

    assert conversation_history.calls == []
    assert captured["history"] is None
