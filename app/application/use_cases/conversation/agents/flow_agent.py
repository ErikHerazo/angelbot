from app.application.ports.flow_confirmation_reply_config_repository_port import (
    FlowConfirmationReplyConfigRepositoryPort,
)
from app.application.ports.llm_port import LLMPort
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)

# Reached when the orchestrator routed to "hablar_con_asesor" but business
# hours are closed (check_business_availability returned False) -- asks the
# user to confirm contact details in-chat so a human can follow up later.
# No backend action is taken here; same as the legacy behavior this ports
# forward (see CLAUDE.md's LangGraph migration notes, flow_agent_node).
#
# Bug found via a live test (2026-09-19/20): this node used to *always*
# return the same canned "give me your name/email/phone" text, with zero
# awareness of the conversation -- once the user actually gave those details,
# the bot kept asking again forever, ignoring the answer. The legacy pipeline
# never had this problem because it re-sends the *entire* history to one big
# LLM call every turn, and its prompt has an explicit rule for this exact
# case (constants.py: "SI el usuario dice que ya proporciono sus datos,
# previo a la conversacion; entonces agradece y dile derivaras su caso a un
# asesor"). Ported that same rule here via a small, focused LLM call instead
# of a fully static reply -- the canned text is now only the fallback for
# when nothing's been provided yet, not the only possible answer.
_CHECK_CONTACT_INFO_PROMPT = (
    "Estás revisando una conversación de atención al cliente de una clínica. "
    "El asistente ya le pidió al usuario su nombre, correo y teléfono para derivar su caso a un asesor humano, "
    "porque el horario de atención está cerrado.\n\n"
    "Revisa el historial: si el usuario YA proporcionó esos datos (nombre, correo y/o teléfono) en algún "
    "momento de la conversación, responde agradeciendo y confirmando que su caso será derivado a un asesor -- "
    "NO vuelvas a pedir los datos.\n\n"
    "Si el usuario TODAVÍA NO ha dado esos datos, responde exactamente con este texto, sin cambiar nada: "
    '"{canned_reply}"'
)


def make_flow_agent_node(
    *, llm: LLMPort, flow_confirmation_reply_config: FlowConfirmationReplyConfigRepositoryPort
) -> NodeFn:
    async def flow_agent_node(state: ConversationState) -> dict:
        canned_reply = await flow_confirmation_reply_config.get_reply(state["tenant_id"])
        history = state.get("history", [])

        if not history:
            return {"final_answer": canned_reply}

        messages = [
            {"role": "system", "content": _CHECK_CONTACT_INFO_PROMPT.format(canned_reply=canned_reply)},
            *history,
            {"role": "user", "content": state["user_question"]},
        ]
        try:
            completion = await llm.complete(messages=messages)
            return {"final_answer": completion.get("content") or canned_reply}
        except Exception as exc:
            log.warning("flow_agent: contact-info check failed, using canned reply", error_type=type(exc).__name__)
            return {"final_answer": canned_reply}

    return flow_agent_node
