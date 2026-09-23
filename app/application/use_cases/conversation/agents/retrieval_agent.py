import json
from typing import Optional

from app.application.ports.llm_port import LLMPort
from app.application.ports.prompt_config_repository_port import PromptConfigRepositoryPort
from app.application.ports.retrieval_tools_provider_port import RetrievalToolsProviderPort
from app.application.ports.translation_port import TranslationPort
from app.application.use_cases.conversation.age_signal import age_reinforcement_note
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState
from app.config.settings import MAX_TOOL_ITERATIONS
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


def make_translate_query_node(translation: TranslationPort) -> NodeFn:
    async def translate_query_node(state: ConversationState) -> dict:
        translated = await translation.translate(state["user_question"], from_lang=None, to_lang="es")
        log.debug("Translated query for retrieval", original=state["user_question"], translated=translated)
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

            # Banda 16-17: MINOR_SAFETY_RULE solo restringe a menores de 16,
            # pero el modelo a veces confunde "menor de edad" (umbral legal
            # general, 18) con el umbral específico de esta clínica --
            # confirmado en vivo. patient_age viene de minor_patient_guard_node
            # (única extracción de edad del grafo, ver age_signal.py).
            age_note = age_reinforcement_note(state.get("patient_age"))
            if age_note:
                system_prompt = f"{system_prompt}\n\n{age_note}"

            messages = [
                {"role": "system", "content": system_prompt},
                *state.get("history", []),
                {"role": "user", "content": state.get("translated_query") or state["user_question"]},
            ]

        tool_schemas = await retrieval_tools.get_tool_schemas()
        log.debug("generate_with_tools: sending completion request", message_count=len(messages))
        completion = await llm.complete(messages=messages, tools=tool_schemas, tool_choice="auto")
        log.debug(
            "generate_with_tools: completion received",
            content=completion.get("content"),
            tool_calls=[tc["name"] for tc in (completion.get("tool_calls") or [])],
        )

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
                log.debug("execute_tools: tool succeeded", tool_name=name, arguments=arguments, result=result)
            except Exception as exc:
                log.warning("Retrieval tool call failed", tool_name=name, error_type=type(exc).__name__)
                content = json.dumps({"error": str(exc)})

            tool_results.append({"role": "tool", "tool_call_id": tool_call["id"], "content": content})

        new_count = state.get("tool_call_count", 0) + 1
        log.info("execute_tools: iteration complete", iteration=new_count, tools_called=len(tool_results))
        return {
            "messages": messages + tool_results,
            "tool_call_count": new_count,
        }

    return execute_tools_node


def route_after_generate(state: ConversationState) -> str:
    """
    - Pending tool calls, still under the iteration budget -> keep looping.
    - Pending tool calls, but the budget is spent -> force a wrap-up
      generation (generate_final_node), since the model still "wants" to act
      and needs to be told to stop and answer with what it already has.
    - No tool calls at all -> the model already produced its real, complete
      answer in this same completion (`last_message["content"]`). Route to
      `use_existing_answer` and use it as-is -- routing to `generate_final`
      here was a real bug found via a live test (2026-09-19/20): re-invoking
      the LLM with a "continue your previous answer" reinforcement message,
      when the transcript's last turn is *already* a complete answer, made
      Claude treat the reinforcement as "what's next after that" and reply
      with only a short follow-up question -- silently discarding the whole
      real answer the user was supposed to receive.
    """
    last_message = state["messages"][-1]
    has_tool_calls = bool(last_message.get("tool_calls"))
    under_limit = state.get("tool_call_count", 0) < MAX_TOOL_ITERATIONS

    if has_tool_calls and under_limit:
        route = "execute_tools"
    elif has_tool_calls and not under_limit:
        route = "generate_final"
        log.warning(
            "route_after_generate: hit MAX_TOOL_ITERATIONS with pending tool calls, forcing generate_final",
            tool_call_count=state.get("tool_call_count", 0),
            max_tool_iterations=MAX_TOOL_ITERATIONS,
        )
    else:
        route = "use_existing_answer"

    log.debug("route_after_generate: routing", route=route, has_tool_calls=has_tool_calls)
    return route


def use_existing_answer_node(state: ConversationState) -> dict:
    last_message = state["messages"][-1]
    final_answer = last_message.get("content") or ""
    log.info("use_existing_answer: reusing completion from generate_with_tools", answer_length=len(final_answer))
    return {"final_answer": final_answer}


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
        log.debug("generate_final: messages sent for final answer", messages=messages)

        # tool_choice="none" prevents further calls, but `tools` is still passed
        # (same as the legacy make_completion.py's force_text path) rather than
        # omitted, matching known-working production behavior.
        tool_schemas = await retrieval_tools.get_tool_schemas()
        completion = await llm.complete(messages=messages, tools=tool_schemas, tool_choice="none")
        final_answer = completion.get("content") or ""
        log.info("generate_final: final answer generated", answer_length=len(final_answer))
        log.debug("generate_final: final answer content", final_answer=final_answer)
        return {"final_answer": final_answer}

    return generate_final_node
