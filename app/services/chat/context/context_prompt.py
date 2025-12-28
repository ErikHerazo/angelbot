from app.services.chat.context.conversation_context import ConversationContext


def context_to_system_message(ctx: ConversationContext) -> dict:
    return {
        "role": "system",
        "content": (
            "Conversation context (internal, do not ask the user):\n"
            f"- conversation_id: {ctx.conversation_id}\n"
        )
    }
