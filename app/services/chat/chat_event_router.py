from fastapi import HTTPException
from app.services.chat.models.event import ChatEvent
from app.services.chat.handlers.message_handler import handle_message
from app.services.chat.handlers.trigger_handler import handle_trigger
from app.services.chat.handlers.flow_handler import handle_flow_lead


async def route_chat_event(event: ChatEvent):
    try:
        # Chat evnets (SalesIQ)
        if event.event_type == "message":
            return await handle_message(event)

        if event.event_type == "trigger":
            return handle_trigger()

        # Form events (Zoho Flow)
        if event.event_type == "lead":
            return await handle_flow_lead(event)

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported event type: {event.event_type}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    