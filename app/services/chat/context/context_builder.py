from app.services.chat.zoho_payload import ZohoMessage
from app.services.chat.context.conversation_context import ConversationContext


def build_conversation_context(msg: ZohoMessage) -> ConversationContext:
    visitor = msg.raw.get("visitor", {})

    return ConversationContext(
        session_id=msg.session_id,
        conversation_id=int(msg.conversation_id),
        department_id=str(visitor.get("department_id")),
    )
