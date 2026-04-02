from app.services.chat.models.event import ChatEvent
from app.services.chat.use_cases.process_zoho_flow_lead import process_zoho_flow_lead
from app.services.cloud.azure.azure_openai import run_conversation_with_rag


async def handle_flow_lead(event: ChatEvent):
    return await process_zoho_flow_lead(
        request_id=event.request_id,
        session_id=event.session_id,
        lead_data=event.raw,
        rag_runner=run_conversation_with_rag
    )
