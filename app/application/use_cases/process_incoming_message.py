import logging
from typing import Optional

from app.application.ports.chat_platform_port import ChatPlatformPort
from app.application.ports.conversation_engine_port import ConversationEnginePort
from app.application.ports.conversation_history_port import ConversationHistoryPort
from app.application.ports.reply_compression_port import ReplyCompressionPort
from app.core.utils.count_visible_chars import count_visible_chars

logger = logging.getLogger(__name__)


class ProcessIncomingMessage:
    def __init__(
        self,
        *,
        chat_platform: ChatPlatformPort,
        conversation_engine: ConversationEnginePort,
        conversation_history: ConversationHistoryPort,
        reply_compressor: ReplyCompressionPort,
        channel_character_limits: dict[str, int],
        stateless_channels: set[str],
        fallback_message: str,
        max_history: int,
    ):
        self._chat_platform = chat_platform
        self._conversation_engine = conversation_engine
        self._conversation_history = conversation_history
        self._reply_compressor = reply_compressor
        self._channel_character_limits = channel_character_limits
        self._stateless_channels = stateless_channels
        self._fallback_message = fallback_message
        self._max_history = max_history

    async def execute(
        self,
        *,
        tenant_id: str,
        request_id: str,
        session_id: str,
        user_question: str,
        channel: str,
        visitor_language: Optional[str] = None,
    ) -> None:
        await self._chat_platform.send_progress_update(request_id)

        try:
            answer = await self._conversation_engine.generate_reply(
                tenant_id=tenant_id,
                session_id=session_id,
                user_question=user_question,
                channel=channel,
                visitor_language=visitor_language,
            )
        except Exception:
            logger.exception("Conversation engine failed", extra={"request_id": request_id})
            answer = self._fallback_message

        if not answer:
            answer = self._fallback_message

        char_limit = self._channel_character_limits.get(channel)
        if char_limit and count_visible_chars(answer) > char_limit:
            answer = await self._reply_compressor.compress(answer, user_question)

        if channel not in self._stateless_channels:
            try:
                await self._conversation_history.append_turn(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    user_message=user_question,
                    assistant_message=answer,
                    max_history=self._max_history,
                )
            except Exception:
                logger.exception(
                    "No se pudo guardar el historial de la sesión",
                    extra={"request_id": request_id, "session_id": session_id},
                )

        await self._chat_platform.send_final_response(request_id, answer)
