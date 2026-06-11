from app.services.chat.models.event import ChatEvent
from app.core import constants


def parse_zoho_sales_payload(body: dict) -> ChatEvent:

    handler = body.get("handler")
    message = body.get("message") or {}
    visitor = body.get("visitor") or {}

    request_id = body.get("request", {}).get("id")
    session_id = str(visitor.get("visitor_id"))
    channel = visitor.get("channel")

    meta = message.get("meta") or {}
    card_data = meta.get("card_data")

    message_type = message.get("type")
    attachments = body.get("attachments") or []

    if card_data and card_data.get("id") == "continue":
        user_message = constants.CONTINUE_TOKEN

    elif message_type == "files":
        user_message = None

    elif message.get("text"):
        user_message = message["text"]
    else:
        user_message = None
    print("HANDLER:", handler)
    print("VISITOR_ID:", visitor.get("visitor_id"))
    print("NAME:", visitor.get("name"))
    print("EMAIL:", visitor.get("email"))
    print("PHONE:", visitor.get("phone"))
    return ChatEvent(
        source="salesiq",
        event_type=handler,
        session_id=session_id,
        request_id=request_id,
        lead_id=None,  # 🔴 importante
        user_name=visitor.get("name"),
        user_email=visitor.get("email"),
        user_phone=visitor.get("phone"),
        message=user_message,
        message_type=message_type,
        attachments=attachments,
        intent=None,
        metadata={
            "channel": visitor.get("channel"),
            "language": visitor.get("language"),
        },
        raw=body,
    )
