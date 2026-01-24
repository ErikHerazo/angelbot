from fast_langdetect import detect_language

def resolve_language(text: str) -> str:
    """
    Detects language from text.
    Assumes length validation is handled externally.
    """
    return detect_language(text).lower()
