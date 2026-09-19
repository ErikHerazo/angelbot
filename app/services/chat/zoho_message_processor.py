import os
import logging

from dotenv import load_dotenv

from app.services.zoho.client import ZohoClient
from app.services.cloud.azure.azure_openai import run_conversation_with_rag
from app.services.chat.use_cases.process_zoho_message import process_zoho_message

load_dotenv()

logger = logging.getLogger(__name__)

ZOHO_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN")
zoho_client = ZohoClient(access_token=ZOHO_ACCESS_TOKEN)

async def process_message_async(
    request_id: str,
    session_id: str,
    user_question: str,
    channel: str,
    visitor_language: str | None = None,
):
    try:
        await process_zoho_message(
            zoho_client=zoho_client,
            request_id=request_id,
            session_id=session_id,
            user_question=user_question,
            channel=channel,
            rag_runner=run_conversation_with_rag,
            visitor_language=visitor_language,
        )
    except Exception as e:
        logger.exception(
            "Zoho async processing failed",
            extra={"request_id": request_id},
        )


async def process_message_async_hexagonal(
    *,
    engine: str,
    tenant_id: str,
    request_id: str,
    session_id: str,
    user_question: str,
    channel: str,
    visitor_language: str | None = None,
):
    """Same job as process_message_async (real Zoho webhook, background task),
    but through the hexagonal ProcessIncomingMessage use case with a selectable
    ConversationEnginePort -- the real-traffic counterpart to what
    /web/chat/test-hexagonal already does with synthetic requests. Uses the
    real ChatPlatformPort (ZohoChatPlatformAdapter, not the test-only
    _CapturingChatPlatform), since build_process_incoming_message defaults to
    it when no override is given. Only reached when ZOHO_WEBHOOK_ENGINE is set
    to something other than "legacy" (see message_handler.py) -- gated behind
    its own try/except here because ProcessIncomingMessage.execute() doesn't
    wrap its own send_progress_update/send_final_response calls, and this runs
    detached via asyncio.create_task (an uncaught exception there wouldn't
    crash anything, but would be logged far less usefully than this).
    """
    from app.composition_root import build_process_incoming_message

    try:
        use_case = await build_process_incoming_message(tenant_id, engine=engine)
        await use_case.execute(
            tenant_id=tenant_id,
            request_id=request_id,
            session_id=session_id,
            user_question=user_question,
            channel=channel,
            visitor_language=visitor_language,
        )
    except Exception:
        logger.exception(
            "Hexagonal async processing failed",
            extra={"request_id": request_id, "engine": engine},
        )
        