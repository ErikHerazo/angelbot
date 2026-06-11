from app.core import constants
from app.services.cache.session_memory import SessionMemoryRedis
from app.services.cloud.azure.translate_text import translate_text


session_memory = SessionMemoryRedis()

async def handle_continue_token(
    session_id: str,
    user_question: str,
    channel: str,
) -> str | None:

    # 1. Si no es el token, no aplica
    if user_question != constants.CONTINUE_TOKEN:
        return None

    # 2. Caso especial: canal flow → respuesta vacía
    if channel == "flow":
        return ""

    lang = await session_memory.get_language(session_id)
    print(f"SESSION CONTINUE: {session_id}")
    metadata = await session_memory.get_metadata(session_id)
    print(f"METADATA CONTINUE: {metadata}")
    print(f"🌐 Continue token language: {lang}")

    # 3. Mensaje fijo en español
    message = constants.RESPONSE_TO_THE_CONTINUE_TOKEN_MESSAGE

    if lang and lang != "es":
        message = await translate_text(
            text=message,
            from_lang="es",
            to_lang=lang
        )
    return message
