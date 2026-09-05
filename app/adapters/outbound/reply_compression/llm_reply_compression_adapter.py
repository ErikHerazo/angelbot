from typing import Callable, Optional


class LLMReplyCompressionAdapter:
    """Implements ReplyCompressionPort, wrapping generate_compact_answer.

    `compress_fn` is injected (defaults lazily to the real
    generate_compact_answer) so this adapter is testable without
    constructing a real Azure OpenAI client.
    """

    def __init__(self, *, compress_fn: Optional[Callable] = None):
        if compress_fn is None:
            from app.core.utils.summarize_with_llm import generate_compact_answer

            compress_fn = generate_compact_answer

        self._compress_fn = compress_fn

    async def compress(self, answer: str, original_question: str) -> str:
        return await self._compress_fn(answer, original_question)
