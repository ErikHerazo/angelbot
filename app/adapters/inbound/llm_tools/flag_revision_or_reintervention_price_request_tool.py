import json


class FlagRevisionOrReinterventionPriceRequestTool:
    """Exposes the revision/reintervention-price signal as an LLM tool call.

    No domain/application logic behind this on purpose: this tool carries
    no business rule of its own -- it's a pure signal the LLM raises, and
    the actual deterministic response (REVISION_PRICE_FALLBACK_MESSAGE,
    translated, skipping the final LLM generation pass) is decided by the
    conversation orchestration in azure_openai.py, not by this tool. That
    orchestration hasn't been decomposed out of run_conversation_with_rag
    yet (still wrapped whole behind ConversationEnginePort) -- when it is,
    that's where this flag's effect belongs, not here.
    """

    async def __call__(self, input: str = "") -> str:
        return json.dumps({"acknowledged": True})
