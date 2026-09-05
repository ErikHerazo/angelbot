from typing import Callable, Optional

from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


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
        with log.operation(original_length=len(answer)):
            compressed = await self._compress_fn(answer, original_question)
            log.debug("Compression finished", compressed_length=len(compressed) if compressed else 0)
            return compressed
