from fast_langdetect import detect_language
from app.core import constants


def resolve_language(text: str) -> str:
    if not text:
        return "es"

    try:
        detected = detect_language(text).lower()
    except Exception:
        return "es"

    if detected not in constants.SUPPORTED_LANGUAGES:
        return "es"

    return detected
