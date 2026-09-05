from typing import Awaitable, Callable, Optional

from app.adapters.inbound.llm_tools.check_business_availability_tool import (
    CheckBusinessAvailabilityTool,
)
from app.adapters.inbound.llm_tools.flag_emotional_distress_tool import FlagEmotionalDistressTool
from app.adapters.inbound.llm_tools.flag_minor_patient_tool import FlagMinorPatientTool
from app.adapters.inbound.llm_tools.flag_revision_or_reintervention_price_request_tool import (
    FlagRevisionOrReinterventionPriceRequestTool,
)
from app.adapters.inbound.llm_tools.lookup_procedure_price_tool import LookupProcedurePriceTool
from app.application.ports.conversation_history_port import ConversationHistoryPort
from app.application.ports.prompt_config_repository_port import PromptConfigRepositoryPort
from app.application.use_cases.check_business_availability import CheckBusinessAvailability
from app.application.use_cases.lookup_procedure_price import LookupProcedurePrice
from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


class AzureOpenAIConversationEngineAdapter:
    """Implements ConversationEnginePort, wrapping run_conversation_with_rag.

    `rag_runner` is injected (defaults lazily to the real
    run_conversation_with_rag) instead of imported at module load time, so
    this adapter stays importable/testable without pulling in azure_tools'
    pyodbc dependency chain.

    `check_business_availability` and `get_lookup_procedure_price` are
    optional -- when given, this adapter builds `tool_overrides` per call
    (binding tenant_id to the LLM tool wrappers) and passes them to
    `rag_runner`, bridging the async hexagonal tools into the (still
    synchronous-by-default) legacy tool-dispatch loop. `get_lookup_procedure_price`
    is a callable rather than a plain instance because that use case's
    adapter needs tenant-specific secret/config lookups -- the caller is
    expected to cache it per tenant_id (see composition_root.py) rather than
    rebuild it on every single conversation turn.

    `prompt_config` is also optional -- when given, the per-tenant/channel
    prompt (with MINOR_SAFETY_RULE/DISAMBIGUATION_RULES already substituted)
    is fetched fresh every call and passed as `base_prompt_override`, instead
    of `run_conversation_with_rag` reading the hardcoded AGB-only prompt from
    constants.py. Not cached like the price-lookup tool -- it's a local file
    read, not a secret-manager round trip, so re-reading it per turn is cheap.

    Building `get_lookup_procedure_price(tenant_id)` and reading
    `prompt_config` both do real I/O (secret/config lookups) before the LLM
    is ever called -- if either fails (e.g. a missing per-tenant secret),
    that failure is caught and logged as a warning here, and this method
    degrades gracefully instead of aborting the whole reply: the price tool
    is simply omitted (falls back to the legacy `azure_tools.py` price
    lookup) and/or the prompt override stays `None` (falls back to the
    legacy `constants.py` prompt). One tenant's misconfigured tool should
    never block every message for that tenant.
    """

    def __init__(
        self,
        *,
        conversation_history: ConversationHistoryPort,
        rag_runner: Optional[Callable] = None,
        check_business_availability: Optional[CheckBusinessAvailability] = None,
        get_lookup_procedure_price: Optional[Callable[[str], Awaitable[LookupProcedurePrice]]] = None,
        prompt_config: Optional[PromptConfigRepositoryPort] = None,
    ):
        self._conversation_history = conversation_history
        self._check_business_availability = check_business_availability
        self._get_lookup_procedure_price = get_lookup_procedure_price
        self._prompt_config = prompt_config

        if rag_runner is None:
            from app.services.cloud.azure.azure_openai import run_conversation_with_rag

            rag_runner = run_conversation_with_rag

        self._rag_runner = rag_runner

    async def generate_reply(
        self,
        *,
        tenant_id: str,
        session_id: str,
        user_question: str,
        channel: str,
        visitor_language: Optional[str] = None,
    ) -> str:
        with log.operation(tenant_id=tenant_id, session_id=session_id, channel=channel):
            history = None
            if channel != "flow":
                history = await self._conversation_history.get_history(tenant_id, session_id)
                log.debug("Loaded conversation history", turns=len(history))
            else:
                log.debug("Flow channel, skipping history load")

            tool_overrides = {
                "flag_revision_or_reintervention_price_request": FlagRevisionOrReinterventionPriceRequestTool(),
                "flag_emotional_distress": FlagEmotionalDistressTool(),
                "flag_minor_patient": FlagMinorPatientTool(),
            }

            if self._check_business_availability is not None:
                tool_overrides["is_customer_service_available"] = CheckBusinessAvailabilityTool(
                    use_case=self._check_business_availability,
                    tenant_id=tenant_id,
                )

            if self._get_lookup_procedure_price is not None:
                try:
                    price_use_case = await self._get_lookup_procedure_price(tenant_id)
                    tool_overrides["procedures_and_treatments_price_list"] = LookupProcedurePriceTool(
                        use_case=price_use_case,
                        tenant_id=tenant_id,
                    )
                except Exception as exc:
                    # No dejamos que un secreto/config faltante de ESTA tool
                    # tumbe toda la respuesta -- se omite el override y
                    # run_conversation_with_rag cae al azure_tools.py legacy
                    # para procedures_and_treatments_price_list.
                    log.warning(
                        "No se pudo armar LookupProcedurePrice, se omite el override de esta tool",
                        tenant_id=tenant_id,
                        error_type=type(exc).__name__,
                    )

            log.debug("Tool overrides wired", tools=sorted(tool_overrides.keys()))

            base_prompt_override = None
            if self._prompt_config is not None:
                try:
                    base_prompt_override = await self._prompt_config.get_base_prompt(tenant_id, channel)
                    log.debug("Fetched tenant/channel prompt override", channel=channel)
                except Exception as exc:
                    log.warning(
                        "No se pudo leer el prompt config del tenant, se usa el prompt legacy de constants.py",
                        tenant_id=tenant_id,
                        channel=channel,
                        error_type=type(exc).__name__,
                    )

            answer = await self._rag_runner(
                session_id=session_id,
                user_question=user_question,
                channel=channel,
                visitor_language=visitor_language,
                history=history,
                tool_overrides=tool_overrides,
                base_prompt_override=base_prompt_override,
            )
            log.debug("rag_runner returned", answer_length=len(answer) if answer else 0)
            return answer
