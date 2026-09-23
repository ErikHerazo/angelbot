from app.application.ports.minor_patient_deferral_config_repository_port import (
    MinorPatientDeferralConfigRepositoryPort,
)
from app.application.use_cases.conversation.age_signal import (
    MINOR_AGE_THRESHOLD,
    extract_youngest_age,
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
    """Guarda determinística (sin llamar a ningún LLM): si en el mensaje
    actual o en el historial de la conversación se menciona una edad menor
    a 16 años, corta el flujo y devuelve el mensaje de derivación a
    especialista ya escrito -- deliberadamente sin exigir además que el
    mensaje "pida precio explícitamente" (a diferencia de
    pectus_poland_guard, que sí distingue señales): para un caso de
    seguridad de menores, es preferible derivar de más que de menos.

    Siempre deja `patient_age` en el estado (se dispare o no la guarda) --
    es la única extracción de edad de todo el grafo (ver age_signal.py);
    generate_with_tools_node la reutiliza para la banda 16-17 en vez de
    que cada regla relacionada con edad vuelva a detectarla por su lado.

    Corre después de translate_query_node -- compara `translated_query`
    (ya en español) contra el patrón de edad, igual que pectus_poland_guard,
    para funcionar sin importar el idioma del mensaje actual. El
    historial no se re-traduce (limitación conocida, misma clase que la de
    pectus_poland_guard): una edad mencionada en un turno anterior en otro
    idioma podría no detectarse.
    """

    async def minor_patient_guard_node(state: ConversationState) -> dict:
        current_text = state.get("translated_query") or state.get("user_question") or ""
        history_text = " ".join(
            m.get("content", "")
            for m in (state.get("history") or [])
            if isinstance(m.get("content"), str)
        )
        age = extract_youngest_age(current_text, history_text)

        if age is not None and age < MINOR_AGE_THRESHOLD:
            reply = await deferral_config.get_reply(state["tenant_id"])
            return {"minor_patient_guard_triggered": True, "final_answer": reply, "patient_age": age}

        return {"minor_patient_guard_triggered": False, "patient_age": age}

    return minor_patient_guard_node


def route_after_minor_patient_guard(state: ConversationState) -> str:
    if state.get("minor_patient_guard_triggered"):
        return "enforce_language"
    return "pectus_poland_guard"
