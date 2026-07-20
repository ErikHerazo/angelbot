import asyncio
import logging
import uuid

from app.core import constants
from app.services.chat.models.event import ChatEvent
from app.services.chat.zoho_message_processor import process_message_async
from app.core.utils.resolve_reply_language import resolve_reply_language
from app.services.cloud.azure.translate_text import translate_text


logger = logging.getLogger(__name__)

async def handle_message(event: ChatEvent):
    session_id = event.session_id or str(uuid.uuid4())
    channel = event.metadata.get("channel")
    visitor_language = event.metadata.get("language")

    # 🚨 BLOQUEO MULTIMEDIA
    if event.message_type == "files":
        lang = await resolve_reply_language(
            session_id=session_id,
            language_hint=visitor_language,
        )

        message = "✅ Archivo subido con éxito."

        if lang != "es":
            message = await translate_text(
                text=message,
                from_lang="es",
                to_lang=lang,
            )

        return {
            "action": "reply",
            "replies": [{
                "type": "text",
                "text": message
            }]
        }
    else:
        asyncio.create_task(
            process_message_async(
                request_id=event.request_id,
                session_id=session_id,
                user_question=event.message,
                channel=channel,
                visitor_language=visitor_language,
            )
        )

        return constants.PENDING_PAYLOAD
