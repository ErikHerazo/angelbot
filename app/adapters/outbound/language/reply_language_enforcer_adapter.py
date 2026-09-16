from typing import Callable, Optional


class ReplyLanguageEnforcerAdapter:
    """Implements ReplyLanguageEnforcerPort, wrapping the legacy
    enforce_reply_language (core/utils/enforce_reply_language.py) -- the
    final safety net that detects the LLM's actual output language and
    translates it if it doesn't match the resolved reply_language.

    `enforce_fn` is injected (defaults lazily to the real function) for
    testability, same pattern as rag_runner/resolve_fn elsewhere in this
    migration.
    """

    def __init__(self, *, enforce_fn: Optional[Callable] = None):
        if enforce_fn is None:
            from app.core.utils.enforce_reply_language import enforce_reply_language

            enforce_fn = enforce_reply_language

        self._enforce_fn = enforce_fn

    async def enforce(self, answer: str, reply_language: str) -> str:
        return await self._enforce_fn(answer, reply_language)
