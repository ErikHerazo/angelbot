from app.services.cloud.azure.azure_language_detector import detect_language_azure
from app.services.cloud.azure.translate_text import translate_text
from app.core.logging_config import logger


async def enforce_same_language(input_text: str, output_text: str) -> str:
    """
    Garantiza que output_text mantenga el mismo idioma que input_text.
    Si no coincide, traduce output al idioma del input.
    """

    input_lang = await detect_language_azure(input_text)
    output_lang = await detect_language_azure(output_text)

    if not input_lang or not output_lang:
        return output_text

    if input_lang == output_lang:
        return output_text

    logger.info(
        f"Language mismatch detected: input={input_lang}, output={output_lang}. Translating output..."
    )

    try:
        translated = await translate_text(
            text=output_text,
            from_lang=output_lang,
            to_lang=input_lang
        )
        return translated

    except Exception:
        logger.exception("Language enforcement failed")
        return output_text
    