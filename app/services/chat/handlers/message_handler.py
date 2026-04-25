import asyncio
import logging
import uuid

from app.core import constants
from app.services.chat.models.event import ChatEvent
from app.services.chat.zoho_message_processor import process_message_async


logger = logging.getLogger(__name__)

def handle_message(event: ChatEvent):
    session_id = event.session_id or str(uuid.uuid4())
    print(f"mensaje de entrada por el webhook: {event.message}")
    asyncio.create_task(
        process_message_async(
            request_id=event.request_id,
            session_id=session_id,
            user_question=event.message,
            channel=event.metadata.get("channel"),
        )
    )

    return constants.PENDING_PAYLOAD
