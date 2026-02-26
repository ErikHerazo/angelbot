from fast_langdetect import detect_language
from app.core import constants


MIN_CONFIDENCE_LEN = 5

def resolve_language(text: str, current_session_lang: str | None = None) -> str:
    """
    Detecta idioma de forma robusta:
    - Mantiene idioma actual si el mensaje es corto
    - Solo permite idiomas definidos en constants.SUPPORTED_LANGUAGES
    - Fallback limpio si hay error
    """

    # 1️⃣ Mensajes muy cortos no cambian idioma
    if not text or len(text.strip()) < MIN_CONFIDENCE_LEN:
        return current_session_lang or "es"

    try:
        detected = detect_language(text).lower()
    except Exception:
        return current_session_lang or "es"

    # 2️⃣ Validar contra idiomas soportados globalmente
    if detected not in constants.SUPPORTED_LANGUAGES:
        return current_session_lang or "es"

    return detected
