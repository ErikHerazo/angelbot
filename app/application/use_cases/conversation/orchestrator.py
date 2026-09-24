from app.application.ports.llm_port import LLMPort
from app.application.use_cases.check_business_availability import CheckBusinessAvailability
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)

CLASSIFY_INTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "classify_intent",
        "description": "Classify what the user is trying to do, to route the conversation.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": ["hablar_con_asesor", "agendar_cita", "info_general"],
                    "description": (
                        "'hablar_con_asesor' if the user explicitly wants to talk to a human/advisor/customer "
                        "service. 'agendar_cita' if the user wants to book/schedule an appointment, visit or "
                        "consultation in general. 'info_general' for everything else (procedure info, prices, "
                        "general questions), including when the user has already chosen the free evaluation "
                        "by sending photos/email -- that needs a contextual answer, not the booking options again."
                    ),
                }
            },
            "required": ["intent"],
        },
    },
}

_FORCE_CLASSIFY_INTENT = {"type": "function", "function": {"name": "classify_intent"}}


def make_orchestrator_node(
    *,
    llm: LLMPort,
    check_business_availability: CheckBusinessAvailability,
) -> NodeFn:
    async def orchestrator_node(state: ConversationState) -> dict:
        with log.operation(tenant_id=state["tenant_id"], session_id=state["session_id"]):
            messages = [
                {
                    "role": "system",
                    "content": "Clasifica la intención del último mensaje del usuario llamando a classify_intent.",
                },
                *state.get("history", []),
                {"role": "user", "content": state["user_question"]},
            ]

            log.debug("orchestrator_node: classification request", messages=messages)
            completion = await llm.complete(
                messages=messages, tools=[CLASSIFY_INTENT_TOOL], tool_choice=_FORCE_CLASSIFY_INTENT
            )
            log.debug("orchestrator_node: classification response", completion=completion)

            intent = "info_general"
            tool_calls = completion.get("tool_calls")
            if tool_calls:
                intent = tool_calls[0]["arguments"].get("intent", "info_general")

            if intent == "hablar_con_asesor":
                available = await check_business_availability.execute(state["tenant_id"])
                route = "direct" if available else "flow"
            elif intent == "agendar_cita":
                route = "agenda"
            else:
                route = "retrieval"

            log.info("Orchestrator routed conversation", intent=intent, route=route)
            return {"route": route}

    return orchestrator_node


def route_after_orchestrator(state: ConversationState) -> str:
    return state["route"]
