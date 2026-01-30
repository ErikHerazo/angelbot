from dataclasses import dataclass
from typing import Optional
from app.core import constants

@dataclass
class ZohoMessage:
    handler: str
    request_id: Optional[str]
    session_id: str
    user_question: Optional[str]
    raw: dict

def parse_zoho_payload(body: dict) -> ZohoMessage:
    handler = body.get("handler")
    message = body.get("message") or {}
    visitor = body.get("visitor") or {}

    request_id = body.get("request", {}).get("id")
    session_id = visitor.get("visitor_id")

    meta = message.get("meta") or {}
    card_data = meta.get("card_data")

    if card_data and card_data.get("id") == "continue":
        user_question = constants.CONTINUE_TOKEN
    elif message.get("text"):
        user_question=message["text"]
    else:
        user_question = None

    return ZohoMessage(
        handler=handler,
        request_id=request_id,
        session_id=session_id,
        user_question=user_question,
        raw=body,
    )
