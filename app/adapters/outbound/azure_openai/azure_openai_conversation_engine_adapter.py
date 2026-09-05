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
        history = None
        if channel != "flow":
            history = await self._conversation_history.get_history(tenant_id, session_id)

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
            price_use_case = await self._get_lookup_procedure_price(tenant_id)
            tool_overrides["procedures_and_treatments_price_list"] = LookupProcedurePriceTool(
                use_case=price_use_case,
                tenant_id=tenant_id,
            )

        base_prompt_override = None
        if self._prompt_config is not None:
            base_prompt_override = await self._prompt_config.get_base_prompt(tenant_id, channel)

        return await self._rag_runner(
            session_id=session_id,
            user_question=user_question,
            channel=channel,
            visitor_language=visitor_language,
            history=history,
            tool_overrides=tool_overrides,
            base_prompt_override=base_prompt_override,
        )
