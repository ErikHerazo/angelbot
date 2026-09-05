from typing import Optional, Protocol


class ReplyLanguageResolverPort(Protocol):
    async def resolve(
        self,
        *,
        tenant_id: str,
        session_id: str,
        current_message: Optional[str] = None,
        language_hint: Optional[str] = None,
        use_history: bool = True,
    ) -> str: ...
