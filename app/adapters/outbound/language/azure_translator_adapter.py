from typing import Callable, Optional


class AzureTranslatorAdapter:
    """Implements TranslationPort, wrapping translate_text.

    `translate_fn` is injected (defaults lazily to the real translate_text)
    for testability without needing a real Azure Translator key.
    """

    def __init__(self, *, translate_fn: Optional[Callable] = None):
        if translate_fn is None:
            from app.services.cloud.azure.translate_text import translate_text

            translate_fn = translate_text

        self._translate_fn = translate_fn

    async def translate(self, text: str, *, from_lang: Optional[str], to_lang: str) -> str:
        return await self._translate_fn(text=text, from_lang=from_lang, to_lang=to_lang)
