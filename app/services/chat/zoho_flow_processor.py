import os
import logging

from dotenv import load_dotenv

from app.services.zoho.client import ZohoClient
from app.services.chat.use_cases.process_zoho_flow_lead import process_zoho_flow_lead

load_dotenv()

logger = logging.getLogger(__name__)

ZOHO_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN")
zoho_client = ZohoClient(access_token=ZOHO_ACCESS_TOKEN)


async def process_flow_lead_async(
    request_id: str,
    session_id: str,
    lead_data: dict,
):
    try:
        await process_zoho_flow_lead(
            zoho_client=zoho_client,
            request_id=request_id,
            session_id=session_id,
            lead_data=lead_data,
        )

    except Exception as e:
        logger.exception(
            "Zoho Flow async processing failed",
            extra={"request_id": request_id},
        )
        