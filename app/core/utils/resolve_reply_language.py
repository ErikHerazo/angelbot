from app.core import constants
from app.core.utils.text_cleaner import get_text_for_language_detection
from app.services.cache.session_memory import SessionMemoryRedis
from app.services.cloud.azure.azure_language_detector import detect_language_azure

session_memory = SessionMemoryRedis()

RESOLVED_LANGUAGE_META_KEY = "resolved_language"


def _normalize_lang_code(lang: str) -> str:
    return lang.split("-")[0].strip().lower()


async def _remember_resolved_language(session_id: str, lang: str) -> None:
    # Guarda el idioma resuelto como estado de sesión (session:{id}:meta,
    # mismo mecanismo -- hasta ahora sin usar -- que ya mantiene
    # SessionMemoryRedis con su propio TTL) para que un mensaje corto o
    # genérico más adelante en la misma conversación no lo "haga olvidar".
    # Un fallo de Redis aquí no debe tumbar la resolución de idioma.
    try:
        await session_memory.update_metadata(session_id, RESOLVED_LANGUAGE_META_KEY, lang)
    except Exception:
        pass


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
      0. El idioma ya "recordado" para esta sesión (guardado en un turno
         anterior), salvo que el mensaje actual traiga señal lingüística
         fuerte de un cambio real de idioma (ver MIN_LANG_SWITCH_DETECTION_LEN).
      1. El mensaje actual del usuario, si trae suficiente señal lingüística.
      2. El historial de turnos del usuario en la sesión (mensajes cortos o
         ambiguos como "hi", "ok", "sí" no bastan por sí solos).
      3. Un idioma declarado externamente (idioma del visitante que reporta
         Zoho SalesIQ, o el idioma declarado en un formulario de Zoho Flow).
      4. Español por defecto.

    El paso 0 existe porque detectar el idioma turno a turno, solo a partir
    del mensaje actual, hacía que mensajes cortos y genéricos ("aumentar",
    "sí, dime", un nombre propio, lo que sobrevive de un email tras
    limpiarlo) "le hicieran perder" a la sesión el idioma ya establecido --
    Azure detecta *algo* sobre ese texto corto, pero no es una señal fiable
    de que el usuario cambió de idioma. Una vez que la sesión ya tiene un
    idioma recordado, hace falta más señal (MIN_LANG_SWITCH_DETECTION_LEN,
    no solo MIN_LANG_DETECTION_LEN) en el mensaje actual para reemplazarlo
    -- así un cambio de idioma real (una frase larga y clara en otro idioma)
    sigue detectándose con normalidad.
    """
    sticky_lang = None
    if use_history:
        try:
            metadata = await session_memory.get_metadata(session_id)
            sticky_lang = metadata.get(RESOLVED_LANGUAGE_META_KEY)
        except Exception:
            sticky_lang = None

    if current_message:
        clean_current = get_text_for_language_detection(current_message)
        required_len = (
            constants.MIN_LANG_SWITCH_DETECTION_LEN
            if sticky_lang
            else constants.MIN_LANG_DETECTION_LEN
        )
        if len(clean_current) >= required_len:
            lang = await detect_language_azure(clean_current)
            if lang:
                if use_history:
                    await _remember_resolved_language(session_id, lang)
                return lang

    if sticky_lang:
        return sticky_lang

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
                    await _remember_resolved_language(session_id, lang)
                    return lang

    if language_hint and language_hint.replace("-", "").isalpha():
        lang = _normalize_lang_code(language_hint)
        if use_history:
            await _remember_resolved_language(session_id, lang)
        return lang

    return "es"
