import asyncio
import logging
import uuid

from app.core import constants
from app.services.chat.zoho_payload import ZohoMessage
from app.services.chat.zoho_processor import process_message_async

logger = logging.getLogger(__name__)

def handle_message(zoho_message: ZohoMessage):
    session_id = zoho_message.session_id or str(uuid.uuid4())

    logger.info(
        "Message webhook received",
        extra={
            "handler": zoho_message.handler,
            "session_id": session_id,
            "has_question": bool(zoho_message.user_question),
        },
    )

    # ✔️ Execute asynchronous task after return
    asyncio.create_task(
        process_message_async(
            request_id=zoho_message.request_id,
            session_id=session_id,
            conversation_id=zoho_message.conversation_id,
            user_question=zoho_message.user_question
        )
    )
    return constants.PENDING_PAYLOAD
