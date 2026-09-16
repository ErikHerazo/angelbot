from app.adapters.outbound.language.reply_language_enforcer_adapter import ReplyLanguageEnforcerAdapter


async def test_delegates_to_injected_enforce_fn():
    calls = []

    async def fake_enforce_fn(answer, reply_lang):
        calls.append((answer, reply_lang))
        return "enforced"

    adapter = ReplyLanguageEnforcerAdapter(enforce_fn=fake_enforce_fn)

    result = await adapter.enforce("hola", "en")

    assert result == "enforced"
    assert calls == [("hola", "en")]
