from app.adapters.outbound.language.azure_translator_adapter import AzureTranslatorAdapter


async def test_delegates_to_injected_translate_fn():
    calls = []

    async def fake_translate_fn(*, text, from_lang, to_lang):
        calls.append((text, from_lang, to_lang))
        return "translated"

    adapter = AzureTranslatorAdapter(translate_fn=fake_translate_fn)

    result = await adapter.translate("hola", from_lang="es", to_lang="en")

    assert result == "translated"
    assert calls == [("hola", "es", "en")]
