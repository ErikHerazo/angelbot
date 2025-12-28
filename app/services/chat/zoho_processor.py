import os
import logging

from dotenv import load_dotenv

from app.services.zoho.client import ZohoClient
from app.services.cloud.azure.azure_openai import run_conversation_with_rag
from app.services.chat.context.conversation_context import ConversationContext
from app.services.chat.use_cases.process_zoho_message import process_zoho_message


load_dotenv()

logger = logging.getLogger(__name__)

ZOHO_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN")
zoho_client = ZohoClient(access_token=ZOHO_ACCESS_TOKEN)

async def process_message_async(request_id: str, session_id: str, conversation_id: str, user_question: str):
    context = ConversationContext(
        session_id=session_id,
        conversation_id=conversation_id,
    )

    try:
        await process_zoho_message(
            zoho_client=zoho_client,
            request_id=request_id,
            context=context,
            user_question=user_question,
            rag_runner=run_conversation_with_rag,
        )
    except Exception as e:
        logger.exception(
            "Zoho async processing failed",
            extra={"request_id": request_id},
        )
        