from app.core import constants
from app.core.utils.text_cleaner import get_text_for_language_detection
from app.services.cache.session_memory import SessionMemoryRedis
from app.services.cloud.azure.azure_language_detector import detect_language_azure

session_memory = SessionMemoryRedis()


async def detect_session_language(session_id: str) -> str:
    """
    Detecta el idioma de una sesión analizando los mensajes del usuario en el
    historial, sin cachear el resultado. Pensado para mensajes fijos que no
    pasan por el LLM (confirmaciones de archivo, mensaje del token de continuar).
    """
    history = await session_memory.get_session(session_id)
    user_texts = [m["content"] for m in history if m.get("role") == "user"]

    if not user_texts:
        return "es"

    clean_text = get_text_for_language_detection(" ".join(user_texts))

    if not clean_text or len(clean_text) < constants.MIN_LANG_DETECTION_LEN:
        return "es"

    lang = await detect_language_azure(clean_text)
    return lang or "es"
