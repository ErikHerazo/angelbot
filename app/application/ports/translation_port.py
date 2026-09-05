from typing import Optional, Protocol


class TranslationPort(Protocol):
    async def translate(self, text: str, *, from_lang: Optional[str], to_lang: str) -> str: ...
