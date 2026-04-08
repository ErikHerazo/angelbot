from fast_langdetect import detect_language as _detect_language
from app.core import constants


detect_language = lambda text: (lang if text and (lang := _detect_language(text).lower()) in constants.SUPPORTED_LANGUAGES else None)
