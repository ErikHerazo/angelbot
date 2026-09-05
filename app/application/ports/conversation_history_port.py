from typing import Protocol


class ConversationHistoryPort(Protocol):
    async def get_history(self, tenant_id: str, session_id: str) -> list[dict]: ...

    async def append_turn(
        self,
        *,
        tenant_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str,
        max_history: int,
    ) -> None: ...
