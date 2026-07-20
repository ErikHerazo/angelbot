from app.core import constants
from app.core.utils.resolve_reply_language import resolve_reply_language
from app.services.cloud.azure.translate_text import translate_text


async def handle_continue_token(
    session_id: str,
    user_question: str,
    channel: str,
    visitor_language: str | None = None,
) -> str | None:

    # 1. Si no es el token, no aplica
    if user_question != constants.CONTINUE_TOKEN:
        return None

    # 2. Caso especial: canal flow → respuesta vacía
    if channel == "flow":
        return ""

    # Este mensaje es fijo y no pasa por el LLM, así que su idioma se
    # detecta al vuelo a partir del historial (sin cachear nada).
    lang = await resolve_reply_language(
        session_id=session_id,
        language_hint=visitor_language,
    )
    print(f"🌐 Continue token language: {lang}")

    # 3. Mensaje fijo en español
    message = constants.RESPONSE_TO_THE_CONTINUE_TOKEN_MESSAGE

    if lang != "es":
        message = await translate_text(
            text=message,
            from_lang="es",
            to_lang=lang
        )
    return message
