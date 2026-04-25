from app.core import constants
from app.services.cloud.azure.translate_text import translate_text


async def validate_supported_language(lang: str | None) -> str | None:
    base_message_es = constants.SUPPORTED_LANGUAGES_MESSAGE

    if not lang:
        return None

    if lang in constants.MAP_ALLOWED_LANG:
        return None

    try:
        translated = await translate_text(
            text=base_message_es,
            from_lang="es",
            to_lang=lang
        )
        return translated or base_message_es
    except Exception:
        return base_message_es
    