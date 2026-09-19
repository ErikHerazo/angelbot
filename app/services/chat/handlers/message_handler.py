import asyncio
import logging
import os
import uuid

from app.core import constants
from app.services.chat.models.event import ChatEvent
from app.services.chat.zoho_message_processor import process_message_async, process_message_async_hexagonal
from app.core.utils.resolve_reply_language import resolve_reply_language
from app.services.cloud.azure.translate_text import translate_text


logger = logging.getLogger(__name__)

# Cutover switch for the real Zoho webhook path -- "legacy" (default, zero
# behavior change) keeps using process_message_async (run_conversation_with_rag).
# Any other value ("azure_openai" | "claude" | "langgraph") routes real
# incoming messages through the hexagonal ProcessIncomingMessage use case
# instead, via process_message_async_hexagonal -- same engine names
# /web/chat/test-hexagonal already accepts. Single-tenant today (AGB), same
# as chat_test_hexagonal.py's TENANT_ID constant -- revisit if a second
# tenant is ever onboarded onto the real Zoho webhook.
ZOHO_WEBHOOK_ENGINE = os.getenv("ZOHO_WEBHOOK_ENGINE", "legacy")
TENANT_ID = "agb"

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
        if ZOHO_WEBHOOK_ENGINE == "legacy":
            asyncio.create_task(
                process_message_async(
                    request_id=event.request_id,
                    session_id=session_id,
                    user_question=event.message,
                    channel=channel,
                    visitor_language=visitor_language,
                )
            )
        else:
            asyncio.create_task(
                process_message_async_hexagonal(
                    engine=ZOHO_WEBHOOK_ENGINE,
                    tenant_id=TENANT_ID,
                    request_id=event.request_id,
                    session_id=session_id,
                    user_question=event.message,
                    channel=channel,
                    visitor_language=visitor_language,
                )
            )

        return constants.PENDING_PAYLOAD
