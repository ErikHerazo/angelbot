import os
import uuid

from fastapi import APIRouter, HTTPException, Header

from app.composition_root import build_process_incoming_message
from app.core.logging.structured_logger import get_logger
from app.web.routes.chat_test import ChatTestRequest, ChatTestResponse

log = get_logger(__name__)

router = APIRouter(tags=["testing"])

CHAT_TEST_SECRET = os.getenv("CHAT_TEST_SECRET")
TENANT_ID = "agb"


class _CapturingChatPlatform:
    """Stands in for a real ChatPlatformPort (Zoho, etc.) -- captures the
    final answer instead of delivering it anywhere, so this synchronous
    HTTP test endpoint can return it in the response body."""

    def __init__(self):
        self.final_answer: str | None = None

    async def send_progress_update(self, request_id: str) -> None:
        pass

    async def send_final_response(self, request_id: str, answer_text: str) -> None:
        self.final_answer = answer_text


@router.post("/test-hexagonal", response_model=ChatTestResponse)
async def chat_test_hexagonal(
    payload: ChatTestRequest,
    x_test_secret: str | None = Header(default=None),
):
    """
    Mismo contrato que /web/chat/test (mismo request/response, mismo gate
    por CHAT_TEST_SECRET), pero corre el mensaje a través del pipeline
    hexagonal (ProcessIncomingMessage) en vez de llamar
    run_conversation_with_rag directamente. El historial de sesión lo
    maneja ProcessIncomingMessage internamente (vía ConversationHistoryPort,
    con clave por tenant) -- este endpoint no lo gestiona a mano, a
    diferencia de /test.

    Solo de pruebas, igual que /test: deshabilitado por defecto (404) a
    menos que CHAT_TEST_SECRET esté definido, y requiere el header
    X-Test-Secret con el mismo valor.
    """
    if not CHAT_TEST_SECRET:
        raise HTTPException(status_code=404, detail="Not found")

    if x_test_secret != CHAT_TEST_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    with log.operation(channel=payload.channel):
        session_id = payload.session_id or f"test-{uuid.uuid4()}"
        request_id = str(uuid.uuid4())

        chat_platform = _CapturingChatPlatform()
        use_case = await build_process_incoming_message(TENANT_ID, chat_platform=chat_platform)

        await use_case.execute(
            tenant_id=TENANT_ID,
            request_id=request_id,
            session_id=session_id,
            user_question=payload.message,
            channel=payload.channel,
            visitor_language=payload.visitor_language,
        )

        return ChatTestResponse(session_id=session_id, answer=chat_platform.final_answer or "")
