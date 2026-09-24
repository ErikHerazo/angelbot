import json
from typing import Any, Callable, Optional

from app.application.ports.llm_port import LLMCompletion
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


class ClaudeFoundryLLMAdapter:
    """Implements LLMPort using Claude (Sonnet 5) via Microsoft Foundry.

    This adapter is *only* the raw completion call -- this graph's nodes already own
    history, language, prompting and retrieval explicitly. It exists purely
    to translate between LLMPort's OpenAI-shaped wire format (what every
    node in agents/retrieval_agent.py and orchestrator.py already speaks,
    same as AzureOpenAILLMAdapter) and Claude's native message/tool format,
    so no node needs to know which provider is actually answering.

    `max_tokens` defaults to 8192, not a smaller number -- this deployment's
    extended thinking is on by default and shares the same token budget as
    the visible text; a real production bug (documented in CLAUDE.md under
    "Reliability fixes from a partner's blind comparison test") was traced
    to a too-small max_tokens silently starving the text block. Reusing the
    already-validated value here, not re-deriving it.

    No `temperature` control: tried adding one (mirroring AzureOpenAILLMAdapter's
    already-tuned `temperature=0.2`, to fix a live-reproduced run-to-run
    tool-calling/disambiguation-adherence inconsistency), but confirmed live
    that this SDK's `AsyncMessages.create` (both `AsyncAnthropicFoundry` and
    plain `AsyncAnthropic`, this SDK version) does not accept `temperature`,
    `top_p` or `top_k` at all -- not Foundry-specific, and consistent with
    this deployment's extended thinking being mandatory/default-on for this
    model family (Anthropic requires `temperature=1` when thinking is
    enabled, so the API surface likely omits the knob entirely rather than
    accept-and-ignore it). No inference-level determinism lever available
    here; see CLAUDE.md/memory for what was tried instead.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        deployment: str,
        max_tokens: int = 8192,
        messages_create_fn: Optional[Callable[..., Any]] = None,
    ):
        self._deployment = deployment
        self._max_tokens = max_tokens

        if messages_create_fn is None:
            from anthropic import AsyncAnthropicFoundry

            client = AsyncAnthropicFoundry(api_key=api_key, base_url=endpoint)

            async def _default_messages_create_fn(*, system, messages, tools, tool_choice):
                kwargs: dict = {}
                if tools:
                    kwargs["tools"] = tools
                if tool_choice is not None:
                    kwargs["tool_choice"] = tool_choice
                return await client.messages.create(
                    model=self._deployment,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=messages,
                    **kwargs,
                )

            messages_create_fn = _default_messages_create_fn

        self._messages_create_fn = messages_create_fn

    async def complete(
        self,
        *,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[Any] = None,
    ) -> LLMCompletion:
        system, claude_messages = self._to_claude_messages(messages)
        claude_tools = [self._to_claude_tool(t) for t in tools] if tools else []
        claude_tool_choice = self._to_claude_tool_choice(tool_choice)

        log.debug(
            "Claude request",
            system=system,
            messages=claude_messages,
            tool_names=[t.get("name") for t in claude_tools],
            tool_choice=claude_tool_choice,
        )
        response = await self._messages_create_fn(
            system=system, messages=claude_messages, tools=claude_tools, tool_choice=claude_tool_choice
        )
        log.debug("Claude response", stop_reason=response.stop_reason, content_blocks=[b.type for b in response.content])

        if response.stop_reason == "max_tokens":
            log.warning("Claude stopped at max_tokens -- text may be truncated or empty")

        return self._to_completion(response)

    @staticmethod
    def _to_claude_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        system_parts = [m["content"] for m in messages if m["role"] == "system" and m.get("content")]
        system = "\n\n".join(system_parts)

        claude_messages: list[dict] = []
        for m in messages:
            role = m["role"]
            if role == "system":
                continue

            if role == "tool":
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": m["content"],
                }
                if claude_messages and claude_messages[-1]["role"] == "user" and claude_messages[-1].get("_tool_results"):
                    claude_messages[-1]["content"].append(tool_result_block)
                else:
                    claude_messages.append({"role": "user", "content": [tool_result_block], "_tool_results": True})
                continue

            if role == "assistant" and m.get("tool_calls"):
                content_blocks = []
                if m.get("content"):
                    content_blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"] or "{}"),
                        }
                    )
                claude_messages.append({"role": "assistant", "content": content_blocks})
                continue

            claude_messages.append({"role": role, "content": m.get("content") or ""})

        # Drop the internal bookkeeping key before handing off to the SDK.
        for m in claude_messages:
            m.pop("_tool_results", None)

        return system, claude_messages

    @staticmethod
    def _to_claude_tool(tool: dict) -> dict:
        function = tool["function"]
        return {
            "name": function["name"],
            "description": function.get("description", ""),
            "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
        }

    @staticmethod
    def _to_claude_tool_choice(tool_choice: Optional[Any]) -> Optional[dict]:
        if tool_choice is None:
            return None
        if tool_choice == "auto":
            return {"type": "auto"}
        if tool_choice == "none":
            return {"type": "none"}
        if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
            return {"type": "tool", "name": tool_choice["function"]["name"]}
        return tool_choice

    @staticmethod
    def _to_completion(response: Any) -> LLMCompletion:
        content = next((b.text for b in response.content if b.type == "text"), None)
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        tool_calls = (
            [{"id": b.id, "name": b.name, "arguments": b.input} for b in tool_use_blocks]
            if tool_use_blocks
            else None
        )
        return {"content": content, "tool_calls": tool_calls}
