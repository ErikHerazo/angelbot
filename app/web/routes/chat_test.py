import os
import uuid
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.services.cloud.azure.azure_openai import run_conversation_with_rag
from app.services.cache.session_memory import SessionMemoryRedis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["testing"])

CHAT_TEST_SECRET = os.getenv("CHAT_TEST_SECRET")

# run_conversation_with_rag solo LEE el historial de sesión; guardarlo es
# responsabilidad del llamador (asi lo hace process_zoho_message.py en el
# flujo real). Este endpoint replica ese mismo paso para que las
# conversaciones de prueba mantengan memoria entre turnos igual que en
# produccion - MAX_HISTORY calca la constante usada alli.
session_memory = SessionMemoryRedis()
MAX_HISTORY = 6


class ChatTestRequest(BaseModel):
    message: str
    channel: str = "website"
    session_id: str | None = None
    visitor_language: str | None = None


class ChatTestResponse(BaseModel):
    session_id: str
    answer: str


@router.post("/test", response_model=ChatTestResponse)
async def chat_test(
    payload: ChatTestRequest,
    x_test_secret: str | None = Header(default=None),
):
    """
    Endpoint de solo pruebas: llama directamente a run_conversation_with_rag,
    sin pasar por Zoho ni validar firma de webhook. Pensado para la UI de
    pruebas externa (repo `testing`), no para consumo de Zoho.

    Deshabilitado por defecto (404) a menos que CHAT_TEST_SECRET este
    definido en el .env, y requiere el header X-Test-Secret con el mismo
    valor - el tunel de ngrok ya expone toda la app publicamente, asi que
    esto evita que quede abierto sin querer y generando costo real de
    Azure OpenAI a quien tenga la URL.
    """
    if not CHAT_TEST_SECRET:
        raise HTTPException(status_code=404, detail="Not found")

    if x_test_secret != CHAT_TEST_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session_id = payload.session_id or f"test-{uuid.uuid4()}"

    answer = await run_conversation_with_rag(
        session_id=session_id,
        user_question=payload.message,
        channel=payload.channel,
        visitor_language=payload.visitor_language,
    )

    if payload.channel != "flow":
        try:
            history = await session_memory.get_session(session_id)
            history.append({"role": "user", "content": payload.message})
            history.append({"role": "assistant", "content": answer})
            if len(history) > MAX_HISTORY:
                history = history[-MAX_HISTORY:]
            await session_memory.connect()
            await session_memory.save_session(session_id, history)
        except Exception:
            logger.exception(
                "No se pudo guardar el historial de la sesión de prueba",
                extra={"session_id": session_id},
            )

    return ChatTestResponse(session_id=session_id, answer=answer)
