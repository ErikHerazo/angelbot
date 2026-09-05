from app.core import constants
from app.core.utils.text_cleaner import get_text_for_language_detection
from app.services.cache.session_memory import SessionMemoryRedis
from app.services.cloud.azure.azure_language_detector import detect_language_azure

session_memory = SessionMemoryRedis()


def _normalize_lang_code(lang: str) -> str:
    return lang.split("-")[0].strip().lower()


async def resolve_reply_language(
    session_id: str,
    current_message: str | None = None,
    language_hint: str | None = None,
    use_history: bool = True,
    history: list | None = None,
) -> str:
    """
    Resuelve por código el idioma en el que debe responder el LLM, en vez de
    dejar esa decisión al criterio del modelo. Orden de prioridad:
      1. El mensaje actual del usuario, si trae suficiente señal lingüística.
      2. El historial de turnos del usuario en la sesión (mensajes cortos o
         ambiguos como "hi", "ok", "sí" no bastan por sí solos).
      3. Un idioma declarado externamente (idioma del visitante que reporta
         Zoho SalesIQ, o el idioma declarado en un formulario de Zoho Flow).
      4. Español por defecto.
    """
    if current_message:
        clean_current = get_text_for_language_detection(current_message)
        if len(clean_current) >= constants.MIN_LANG_DETECTION_LEN:
            lang = await detect_language_azure(clean_current)
            if lang:
                return lang

    if use_history:
        if history is None:
            # comportamiento legacy: lee la sesión aquí mismo (sin tenant_id
            # en la clave). Si el caller ya trae el historial -- ej. un
            # adapter que lo obtiene vía ConversationHistoryPort -- se usa
            # tal cual y no se vuelve a leer.
            history = await session_memory.get_session(session_id)
        user_texts = [m["content"] for m in history if m.get("role") == "user"]
        if user_texts:
            clean_history = get_text_for_language_detection(" ".join(user_texts))
            if len(clean_history) >= constants.MIN_LANG_DETECTION_LEN:
                lang = await detect_language_azure(clean_history)
                if lang:
                    return lang

    if language_hint and language_hint.replace("-", "").isalpha():
        return _normalize_lang_code(language_hint)

    return "es"
