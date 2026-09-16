from typing import Protocol


class ReplyLanguageEnforcerPort(Protocol):
    async def enforce(self, answer: str, reply_language: str) -> str: ...
