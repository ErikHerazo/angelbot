from typing import Optional

from app.application.ports.continue_message_config_repository_port import (
    ContinueMessageConfigRepositoryPort,
)
from app.application.ports.reply_language_resolver_port import ReplyLanguageResolverPort
from app.application.ports.translation_port import TranslationPort
from app.core import constants


class InterceptContinuationToken:
    def __init__(
        self,
        *,
        reply_language_resolver: ReplyLanguageResolverPort,
        translator: TranslationPort,
        continue_message_config: ContinueMessageConfigRepositoryPort,
    ):
        self._reply_language_resolver = reply_language_resolver
        self._translator = translator
        self._continue_message_config = continue_message_config

    async def execute(
        self,
        *,
        tenant_id: str,
        session_id: str,
        user_question: str,
        channel: str,
        visitor_language: Optional[str] = None,
    ) -> Optional[str]:
        if user_question != constants.CONTINUE_TOKEN:
            return None

        if channel == "flow":
            return ""

        lang = await self._reply_language_resolver.resolve(
            tenant_id=tenant_id,
            session_id=session_id,
            language_hint=visitor_language,
        )

        message = await self._continue_message_config.get_message(tenant_id)

        if lang != "es":
            message = await self._translator.translate(message, from_lang="es", to_lang=lang)

        return message
