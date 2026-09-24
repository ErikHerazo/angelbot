from app.application.ports.minor_patient_deferral_config_repository_port import (
    MinorPatientDeferralConfigRepositoryPort,
)
from app.application.use_cases.conversation.age_signal import (
    MINOR_AGE_THRESHOLD,
    extract_age_from_user_turn,
    extract_youngest_age_from_history,
    has_price_intent,
)
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState

# MINOR_SAFETY_RULE le instruye al modelo llamar a una función
# `flag_minor_patient` -- pero este pipeline (LangGraph, ver
# McpRetrievalToolsAdapter) solo tiene 2 tools reales conectadas
# (search_price_catalog, search_knowledge_base). Esa función no existe
# aquí, así que el modelo no tiene forma real de cumplir la instrucción --
# confirmado en vivo: en vez de dar precio o derivar correctamente,
# produce una respuesta rota que ni responde ni explica (5/5 reproducible,
# ver memoria de sesion). Esta guarda reemplaza esa instrucción rota por
# un camino determinístico real, mismo patrón que pectus_poland_guard.


def make_minor_patient_guard_node(
    deferral_config: MinorPatientDeferralConfigRepositoryPort,
) -> NodeFn:
    """Guarda determinística (sin llamar a ningún LLM) que corta el flujo y
    devuelve el mensaje de derivación a especialista ya escrito cuando:

    - el usuario da en *este* turno una edad menor de 16 ("tiene 14 años",
      o un "14" suelto respondiendo a la pregunta de edad del bot), o
    - ya dio antes una edad menor de 16 y el mensaje actual pide precio.

    Cualquier otro mensaje posterior (otro tema, "es para mí", angustia...)
    sigue al modelo, que recibe la edad vía `patient_age` +
    age_reinforcement_note. Antes la guarda leía todo el historial (incluidas
    las respuestas del bot) y se disparaba en cada mensaje siguiente de la
    sesión -- confirmado en prod el 2026-09-24.

    Siempre deja `patient_age` en el estado (se dispare o no la guarda) --
    es la única extracción de edad de todo el grafo (ver age_signal.py);
    generate_with_tools_node la reutiliza para la nota de refuerzo.

    Corre después de translate_query_node -- compara `translated_query`
    (ya en español). El historial no se re-traduce (limitación conocida,
    misma clase que la de pectus_poland_guard): una edad mencionada en un
    turno anterior en otro idioma podría no detectarse.
    """

    async def minor_patient_guard_node(state: ConversationState) -> dict:
        current_text = state.get("translated_query") or state.get("user_question") or ""
        history = state.get("history") or []
        previous_assistant_text = next(
            (m.get("content") for m in reversed(history) if m.get("role") == "assistant"),
            None,
        )

        current_age = extract_age_from_user_turn(current_text, previous_assistant_text)
        history_age = extract_youngest_age_from_history(history)
        known_ages = [a for a in (current_age, history_age) if a is not None]
        age = min(known_ages) if known_ages else None

        age_given_now = current_age is not None and current_age < MINOR_AGE_THRESHOLD
        price_asked_for_known_minor = (
            history_age is not None and history_age < MINOR_AGE_THRESHOLD and has_price_intent(current_text)
        )

        if age_given_now or price_asked_for_known_minor:
            reply = await deferral_config.get_reply(state["tenant_id"])
            return {"minor_patient_guard_triggered": True, "final_answer": reply, "patient_age": age}

        return {"minor_patient_guard_triggered": False, "patient_age": age}

    return minor_patient_guard_node


def route_after_minor_patient_guard(state: ConversationState) -> str:
    if state.get("minor_patient_guard_triggered"):
        return "enforce_language"
    return "pectus_poland_guard"
