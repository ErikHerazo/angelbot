from typing import Optional

from app.application.ports.file_upload_ack_config_repository_port import (
    FileUploadAckConfigRepositoryPort,
)
from app.application.ports.reply_language_resolver_port import ReplyLanguageResolverPort
from app.application.ports.translation_port import TranslationPort


class AcknowledgeFileUpload:
    def __init__(
        self,
        *,
        reply_language_resolver: ReplyLanguageResolverPort,
        translator: TranslationPort,
        file_upload_ack_config: FileUploadAckConfigRepositoryPort,
    ):
        self._reply_language_resolver = reply_language_resolver
        self._translator = translator
        self._file_upload_ack_config = file_upload_ack_config

    async def execute(
        self,
        *,
        tenant_id: str,
        session_id: str,
        visitor_language: Optional[str] = None,
    ) -> str:
        lang = await self._reply_language_resolver.resolve(
            tenant_id=tenant_id,
            session_id=session_id,
            language_hint=visitor_language,
        )

        message = await self._file_upload_ack_config.get_message(tenant_id)

        if lang != "es":
            message = await self._translator.translate(message, from_lang="es", to_lang=lang)

        return message
