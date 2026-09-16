import json
from typing import Optional

from app.application.ports.llm_port import LLMPort
from app.application.ports.prompt_config_repository_port import PromptConfigRepositoryPort
from app.application.ports.retrieval_tools_provider_port import RetrievalToolsProviderPort
from app.application.ports.translation_port import TranslationPort
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState
from app.config.settings import MAX_TOOL_ITERATIONS
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


def make_translate_query_node(translation: TranslationPort) -> NodeFn:
    async def translate_query_node(state: ConversationState) -> dict:
        translated = await translation.translate(state["user_question"], from_lang=None, to_lang="es")
        return {"translated_query": translated}

    return translate_query_node


def make_generate_with_tools_node(
    *,
    llm: LLMPort,
    prompt_config: PromptConfigRepositoryPort,
    retrieval_tools: RetrievalToolsProviderPort,
) -> NodeFn:
    async def generate_with_tools_node(state: ConversationState) -> dict:
        messages = state.get("messages")
        if messages is None:
            base_prompt = await prompt_config.get_base_prompt(state["tenant_id"], state["channel"])
            system_prompt = base_prompt.format(reply_language=state["reply_language"])
            messages = [
                {"role": "system", "content": system_prompt},
                *state.get("history", []),
                {"role": "user", "content": state.get("translated_query") or state["user_question"]},
            ]

        tool_schemas = await retrieval_tools.get_tool_schemas()
        completion = await llm.complete(messages=messages, tools=tool_schemas, tool_choice="auto")

        assistant_message: dict = {"role": "assistant", "content": completion.get("content")}
        if completion.get("tool_calls"):
            assistant_message["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                }
                for tc in completion["tool_calls"]
            ]

        return {"messages": messages + [assistant_message]}

    return generate_with_tools_node


def make_execute_tools_node(retrieval_tools: RetrievalToolsProviderPort) -> NodeFn:
    async def execute_tools_node(state: ConversationState) -> dict:
        messages = state["messages"]
        last_message = messages[-1]
        tool_results = []

        for tool_call in last_message.get("tool_calls", []):
            name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"] or "{}")
            try:
                result = await retrieval_tools.call_tool(name, arguments)
                content = json.dumps(result)
            except Exception as exc:
                log.warning("Retrieval tool call failed", tool_name=name, error_type=type(exc).__name__)
                content = json.dumps({"error": str(exc)})

            tool_results.append({"role": "tool", "tool_call_id": tool_call["id"], "content": content})

        return {
            "messages": messages + tool_results,
            "tool_call_count": state.get("tool_call_count", 0) + 1,
        }

    return execute_tools_node


def route_after_generate(state: ConversationState) -> str:
    last_message = state["messages"][-1]
    has_tool_calls = bool(last_message.get("tool_calls"))
    under_limit = state.get("tool_call_count", 0) < MAX_TOOL_ITERATIONS
    return "execute_tools" if (has_tool_calls and under_limit) else "generate_final"


def make_generate_final_node(*, llm: LLMPort, retrieval_tools: RetrievalToolsProviderPort) -> NodeFn:
    async def generate_final_node(state: ConversationState) -> dict:
        # Reinforce the reply-language instruction as a fresh message right
        # before the final generation -- tool results are often in Spanish
        # and can otherwise crowd out the original instruction (same
        # reasoning as the legacy azure_openai.py pipeline, see CLAUDE.md's
        # RAG pipeline section). Deliberately role="user", not "system": a
        # real live run against Claude found it rejects a mid-conversation
        # system message with "This model does not support assistant
        # message prefill. The conversation must end with a user message"
        # (Claude only accepts one system prompt, set once at the start,
        # and requires the transcript to end on a user/tool-result turn
        # before generating).
        # Also found live: phrasing this as a bare imperative ("Responde en
        # inglés") made Claude treat it as a brand-new user request and
        # answer *that* instead of the original question ("Understood, I'll
        # respond in English from now on") -- explicitly framing it as a
        # non-user system reminder that must continue the prior answer
        # fixed it, verified with a real EN multi-turn call.
        reinforcement = {
            "role": "user",
            "content": (
                "[Recordatorio del sistema, no es un mensaje nuevo del usuario: "
                f"continúa y completa tu respuesta a la pregunta anterior, en {state['reply_language']}, "
                "independientemente del idioma de los resultados anteriores.]"
            ),
        }
        messages = state["messages"] + [reinforcement]

        # tool_choice="none" prevents further calls, but `tools` is still passed
        # (same as the legacy make_completion.py's force_text path) rather than
        # omitted, matching known-working production behavior.
        tool_schemas = await retrieval_tools.get_tool_schemas()
        completion = await llm.complete(messages=messages, tools=tool_schemas, tool_choice="none")
        return {"final_answer": completion.get("content") or ""}

    return generate_final_node
