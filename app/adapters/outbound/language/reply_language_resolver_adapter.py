from typing import Callable, Optional

from app.application.ports.conversation_history_port import ConversationHistoryPort


class ReplyLanguageResolverAdapter:
    """Implements ReplyLanguageResolverPort, wrapping resolve_reply_language.

    Fetches history via ConversationHistoryPort (tenant-scoped) and passes
    it in, instead of letting resolve_reply_language self-fetch from the
    legacy, non-tenant-scoped SessionMemoryRedis -- same fix, same reasoning
    as AzureOpenAIConversationEngineAdapter.

    `resolve_fn` is injected (defaults lazily to the real
    resolve_reply_language) for testability, same pattern as rag_runner.
    """

    def __init__(
        self,
        *,
        conversation_history: ConversationHistoryPort,
        resolve_fn: Optional[Callable] = None,
    ):
        self._conversation_history = conversation_history

        if resolve_fn is None:
            from app.core.utils.resolve_reply_language import resolve_reply_language

            resolve_fn = resolve_reply_language

        self._resolve_fn = resolve_fn

    async def resolve(
        self,
        *,
        tenant_id: str,
        session_id: str,
        current_message: Optional[str] = None,
        language_hint: Optional[str] = None,
        use_history: bool = True,
    ) -> str:
        history = None
        if use_history:
            history = await self._conversation_history.get_history(tenant_id, session_id)

        return await self._resolve_fn(
            session_id=session_id,
            current_message=current_message,
            language_hint=language_hint,
            use_history=use_history,
            history=history,
        )
