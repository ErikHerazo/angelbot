import re

from app.application.ports.minor_patient_deferral_config_repository_port import (
    MinorPatientDeferralConfigRepositoryPort,
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
MINOR_AGE_THRESHOLD = 16

_AGE_PATTERN = re.compile(r"\b(\d{1,2})\s*años\b")


def _mentions_minor_age(text: str) -> bool:
    for match in _AGE_PATTERN.findall(text or ""):
        age = int(match)
        if 0 <= age < MINOR_AGE_THRESHOLD:
            return True
    return False


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

        if _mentions_minor_age(current_text) or _mentions_minor_age(history_text):
            reply = await deferral_config.get_reply(state["tenant_id"])
            return {"minor_patient_guard_triggered": True, "final_answer": reply}

        return {"minor_patient_guard_triggered": False}

    return minor_patient_guard_node


def route_after_minor_patient_guard(state: ConversationState) -> str:
    if state.get("minor_patient_guard_triggered"):
        return "enforce_language"
    return "pectus_poland_guard"
