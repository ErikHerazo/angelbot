import re
import unicodedata

from app.application.ports.pectus_poland_disambiguation_config_repository_port import (
    PectusPolandDisambiguationConfigRepositoryPort,
)
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState

# Solo dispara si el mensaje menciona el tema ambiguo (pecho hundido /
# implantes a medida) -- si no aparece ninguna de estas, la guarda no
# aplica y el flujo sigue como si no existiera.
_TRIGGER_TERMS = (
    "pecho hundido",
    "torax hundido",
    "hundimiento del pecho",
    "hundimiento en el pecho",
    "hundimiento del torax",
    "implante a medida",
    "implantes a medida",
)

# Si aparece alguno de estos, el mensaje ya trae la señal que distingue
# Pectus Excavatum (hundimiento central/esternal) de Síndrome de Poland
# (ausencia/subdesarrollo muscular congénito) -- en cualquiera de los dos
# casos, ya hay información suficiente y la guarda deja pasar el mensaje
# sin intervenir.
_DISAMBIGUATING_TERMS = (
    "esternon",
    "centro del pecho",
    "en el centro",
    "en medio del pecho",
    "musculo",
    "muscular",
    "congenito",
    "congenita",
    "de nacimiento",
    "desde que naci",
    "no desarrollo",
    "sin desarrollar",
    "ausencia de pectoral",
    "falta de pectoral",
    "sindrome de poland",
    "pectus excavatum",
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text)


def make_pectus_poland_guard_node(
    disambiguation_config: PectusPolandDisambiguationConfigRepositoryPort,
) -> NodeFn:
    """Guarda determinística (sin llamar a ningún LLM): si el mensaje del
    paciente menciona "pecho hundido"/"implantes a medida" sin traer ninguna
    de las señales que distinguen Pectus Excavatum de Síndrome de Poland,
    corta el flujo ahí mismo y devuelve la pregunta de desambiguación ya
    escrita (mismo patrón que agenda_agent_node/direct_agent_node) -- en vez
    de dejar que Claude decida si pregunta o no, lo cual resultó no ser
    consistente en pruebas en vivo (ver CLAUDE.md / memoria de la sesión
    2026-09-22/23).

    Corre DESPUÉS de translate_query_node -- compara contra
    `translated_query` (ya en español) para funcionar igual sin importar
    el idioma original del mensaje, en vez de mantener una lista de
    palabras clave por idioma.
    """

    async def pectus_poland_guard_node(state: ConversationState) -> dict:
        query = _normalize(state.get("translated_query") or state.get("user_question") or "")

        has_trigger = any(term in query for term in _TRIGGER_TERMS)
        if not has_trigger:
            return {"pectus_poland_guard_triggered": False}

        has_disambiguating_signal = any(term in query for term in _DISAMBIGUATING_TERMS)
        if has_disambiguating_signal:
            return {"pectus_poland_guard_triggered": False}

        question = await disambiguation_config.get_reply(state["tenant_id"])
        return {"pectus_poland_guard_triggered": True, "final_answer": question}

    return pectus_poland_guard_node


def route_after_pectus_poland_guard(state: ConversationState) -> str:
    if state.get("pectus_poland_guard_triggered"):
        return "enforce_language"
    return "generate_with_tools"
