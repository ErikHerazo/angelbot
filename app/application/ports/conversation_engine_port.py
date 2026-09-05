from typing import Optional, Protocol


class ConversationEnginePort(Protocol):
    async def generate_reply(
        self,
        *,
        tenant_id: str,
        session_id: str,
        user_question: str,
        channel: str,
        visitor_language: Optional[str] = None,
    ) -> str: ...
