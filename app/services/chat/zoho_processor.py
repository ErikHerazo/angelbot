import os
import logging

from dotenv import load_dotenv

from app.services.zoho.client import ZohoClient
from app.services.cloud.azure.azure_openai import run_conversation_with_rag


load_dotenv()

logger = logging.getLogger(__name__)

ZOHO_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN")
zoho_client = ZohoClient(access_token=ZOHO_ACCESS_TOKEN)

async def process_message_async(request_id: str, session_id: str, user_question: str):
    try:
        logger.info(
            "Processing Zoho message",
            extra={
                "request_id": request_id,
                "session_id": session_id,
            },
        )
        # 1) Send progress
        await zoho_client.send_progress_update(request_id=request_id)

        # 2) Generate LLM response (RAG)
        answer = await run_conversation_with_rag(session_id, user_question)

        # 3) Send final response
        await zoho_client.send_final_response(request_id=request_id, answer_text=answer)

        logger.info(
            "Zoho response completed",
            extra={"request_id": request_id},
        )
    except Exception as e:
        logger.exception(
            "Zoho async processing failed",
            extra={"request_id": request_id},
        )
        