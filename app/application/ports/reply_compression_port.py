from typing import Protocol


class ReplyCompressionPort(Protocol):
    async def compress(self, answer: str, original_question: str) -> str: ...
