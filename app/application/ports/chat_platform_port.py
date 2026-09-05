from typing import Protocol


class ChatPlatformPort(Protocol):
    async def send_progress_update(self, request_id: str) -> None: ...

    async def send_final_response(self, request_id: str, answer_text: str) -> None: ...
