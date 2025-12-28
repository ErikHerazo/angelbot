from dataclasses import dataclass
from typing import Optional


@dataclass
class ZohoMessage:
    handler: str
    session_id: str
    conversation_id: str
    request_id: Optional[str]
    user_question: Optional[str]
    raw: dict

def parse_zoho_payload(body: dict) -> ZohoMessage:
    handler = body.get("handler")
    message = body.get("message") or {}
    visitor = body.get("visitor") or {}

    request_id = body.get("request", {}).get("id")
    session_id = visitor.get("visitor_id")
    user_question = message.get("text") or visitor.get("question")
    conversation_id = visitor.get("active_conversation_id")

    return ZohoMessage(
        handler=handler,
        request_id=request_id,
        session_id=session_id,
        user_question=user_question,
        conversation_id=conversation_id,
        raw=body,
    )
