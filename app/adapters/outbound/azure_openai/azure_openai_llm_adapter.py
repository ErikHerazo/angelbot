import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncAzureOpenAI,
    InternalServerError,
    RateLimitError,
)

from app.application.ports.llm_port import LLMCompletion
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


class AzureOpenAILLMAdapter:
    """Implements LLMPort against Azure OpenAI, with the same primary/secondary
    failover-with-cooldown behavior as the legacy FailoverLoadBalancer
    (services/cloud/azure/load_balancer.py), ported rather than reused as-is
    since the legacy version reads module-level singleton clients built from
    bare env vars -- here both clients/deployments/generation params are
    constructor-injected, consistent with every other adapter in this
    migration.

    Deliberately talks to the openai SDK directly instead of via LangChain's
    AzureChatOpenAI: this adapter's own manual tool-calling loop (see
    agents/retrieval_agent.py) never uses LangChain's bind_tools/AIMessage
    machinery, so wrapping in LangChain here would add a layer with no
    consumer -- matches this migration's "no premature abstraction" stance.
    """

    DEFAULT_COOLDOWN_SECONDS = 15

    def __init__(
        self,
        *,
        primary_client: AsyncAzureOpenAI,
        secondary_client: AsyncAzureOpenAI,
        deployment_primary: str,
        deployment_secondary: str,
        temperature: float,
        max_tokens: int,
    ):
        self._primary_client = primary_client
        self._secondary_client = secondary_client
        self._deployment_primary = deployment_primary
        self._deployment_secondary = deployment_secondary
        self._temperature = temperature
        self._max_tokens = max_tokens

        self._primary_available = True
        self._primary_retry_at: Optional[datetime] = None

    def _can_try_primary(self) -> bool:
        if self._primary_available:
            return True
        if self._primary_retry_at is None:
            return False
        if datetime.now(timezone.utc) >= self._primary_retry_at:
            self._primary_available = True
            self._primary_retry_at = None
            log.info("PRIMARY re-enabled")
            return True
        return False

    def _block_primary(self, seconds: int) -> None:
        self._primary_available = False
        self._primary_retry_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        log.warning("PRIMARY blocked", cooldown_seconds=seconds, retry_at=self._primary_retry_at.isoformat())

    @staticmethod
    def _extract_retry_after(error: RateLimitError) -> int:
        try:
            response = getattr(error, "response", None)
            if not response:
                return AzureOpenAILLMAdapter.DEFAULT_COOLDOWN_SECONDS

            retry_after = response.headers.get("retry-after")
            if retry_after:
                return max(1, int(float(retry_after)))

            retry_after_ms = response.headers.get("retry-after-ms")
            if retry_after_ms:
                return max(1, int(float(retry_after_ms) / 1000))
        except Exception:
            log.warning("Failed to extract retry-after header")

        return AzureOpenAILLMAdapter.DEFAULT_COOLDOWN_SECONDS

    async def complete(
        self,
        *,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[Any] = None,
    ) -> LLMCompletion:
        async def request(client: AsyncAzureOpenAI, deployment: str):
            kwargs: dict = {}
            if tools is not None:
                kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

            return await client.chat.completions.create(
                model=deployment,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                **kwargs,
            )

        if self._can_try_primary():
            try:
                response = await request(self._primary_client, self._deployment_primary)
            except RateLimitError as e:
                cooldown = self._extract_retry_after(e)
                self._block_primary(cooldown)
                log.warning("Failing over to SECONDARY", reason="RateLimitError", cooldown_seconds=cooldown)
                response = await request(self._secondary_client, self._deployment_secondary)
            except (APITimeoutError, APIConnectionError, InternalServerError) as e:
                self._block_primary(self.DEFAULT_COOLDOWN_SECONDS)
                log.warning("Failing over to SECONDARY", reason=type(e).__name__)
                response = await request(self._secondary_client, self._deployment_secondary)
        else:
            log.info("Using SECONDARY", reason="primary_in_cooldown")
            response = await request(self._secondary_client, self._deployment_secondary)

        return self._to_completion(response)

    @staticmethod
    def _to_completion(response: Any) -> LLMCompletion:
        message = response.choices[0].message
        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments or "{}"),
                }
                for tc in message.tool_calls
            ]
        return {"content": message.content, "tool_calls": tool_calls}
