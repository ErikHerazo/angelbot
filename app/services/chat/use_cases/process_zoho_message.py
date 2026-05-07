import logging
from app.core import constants
from app.services.cache.session_memory import SessionMemoryRedis
from app.core.utils.count_visible_chars import count_visible_chars
from app.core.utils.summarize_with_llm import generate_compact_answer


session_memory = SessionMemoryRedis()
MAX_HISTORY = 6
char_limit = constants.INSTAGRAM_CHARACTER_LIMIT

logger = logging.getLogger(__name__)

async def process_zoho_message(
    *,
    zoho_client,
    request_id: str,
    session_id: str,
    user_question: str,
    channel: str,
    rag_runner,
):

    # 1) Send progress
    await zoho_client.send_progress_update(request_id=request_id)

    # 2) Generate answer (RAG)
    try:
        answer = await rag_runner(session_id, user_question, channel)
        print("===== Respuesta inicial:\n", answer)
        print("===== Longitud aproximada de la respuesta inicial: ", len(answer))
    except Exception:
        logger.exception("RAG failed", extra={"request_id": request_id})
    
        await zoho_client.send_final_response(
            request_id=request_id,
            answer_text=constants.FALLBACK_MESSAGE,
        )
        return
    
    # FALLBACK
    if not answer:
        answer = constants.FALLBACK_MESSAGE

    # 🔥 3) Validación SOLO para Instagram
    if channel == "instagram":
        if count_visible_chars(answer) > char_limit:
            print("===== Respuesta inicial demasiado larga:")
            answer = await generate_compact_answer(answer, user_question)
            print("===== Respuesta optimizada para INSTAGRAM por el modelo de resumen:\n", answer)
            print("===== Longitud resumen:",count_visible_chars(answer))
    
     # 🔥 4) Guardar historial FINAL (lo que realmente ve el usuario)
    if channel != "flow":
        history = await session_memory.get_session(session_id)

        history.append({
            "role": "user",
            "content": user_question
        })

        history.append({
            "role": "assistant",
            "content": answer
        })

        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]

        await session_memory.connect()
        await session_memory.save_session(session_id, history)

    await zoho_client.send_final_response(
        request_id=request_id,
        answer_text=answer,
    )
