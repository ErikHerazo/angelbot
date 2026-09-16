from typing import Awaitable, Callable

from app.application.ports.conversation_history_port import ConversationHistoryPort
from app.application.ports.reply_language_enforcer_port import ReplyLanguageEnforcerPort
from app.application.ports.reply_language_resolver_port import ReplyLanguageResolverPort
from app.application.use_cases.conversation.state import ConversationState

NodeFn = Callable[[ConversationState], Awaitable[dict]]


def make_load_history_node(conversation_history: ConversationHistoryPort, *, max_history: int) -> NodeFn:
    async def load_history_node(state: ConversationState) -> dict:
        history = await conversation_history.get_history(state["tenant_id"], state["session_id"])
        return {"history": history[-max_history:]}

    return load_history_node


def make_resolve_language_node(reply_language_resolver: ReplyLanguageResolverPort) -> NodeFn:
    async def resolve_language_node(state: ConversationState) -> dict:
        reply_language = await reply_language_resolver.resolve(
            tenant_id=state["tenant_id"],
            session_id=state["session_id"],
            current_message=state["user_question"],
            language_hint=state.get("visitor_language"),
            use_history=True,
        )
        return {"reply_language": reply_language}

    return resolve_language_node


def make_enforce_language_node(reply_language_enforcer: ReplyLanguageEnforcerPort) -> NodeFn:
    async def enforce_language_node(state: ConversationState) -> dict:
        enforced = await reply_language_enforcer.enforce(state["final_answer"], state["reply_language"])
        return {"final_answer": enforced}

    return enforce_language_node
