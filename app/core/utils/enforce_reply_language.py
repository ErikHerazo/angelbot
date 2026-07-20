from app.core.utils.text_cleaner import get_text_for_language_detection
from app.services.cloud.azure.azure_language_detector import detect_language_azure
from app.services.cloud.azure.translate_text import translate_text


async def enforce_reply_language(answer: str, reply_lang: str) -> str:
    """
    Última barrera antes de enviar la respuesta al usuario: detecta el
    idioma real de lo que generó el LLM y, si no coincide con el idioma
    que se le había pedido (reply_lang), la traduce. No depende de que el
    LLM haya seguido la instrucción correctamente.
    """
    if not answer or not answer.strip() or not reply_lang:
        return answer

    clean_answer = get_text_for_language_detection(answer)
    if not clean_answer:
        return answer

    detected_lang = await detect_language_azure(clean_answer)
    print(f"🛡️ Idioma detectado en la respuesta del LLM: {detected_lang} (esperado: {reply_lang})")

    if not detected_lang or detected_lang == reply_lang:
        return answer

    print(f"⚠️ Mismatch de idioma, traduciendo respuesta de {detected_lang} a {reply_lang}...")
    translated = await translate_text(text=answer, to_lang=reply_lang)
    return translated or answer
