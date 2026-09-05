import json


class FlagMinorPatientTool:
    """Exposes the minor-patient safety signal as an LLM tool call.

    Same shape as FlagRevisionOrReinterventionPriceRequestTool: no
    domain/application logic behind this -- it's a pure signal the LLM
    raises, and the actual deterministic response (MINOR_SAFETY_PROMPT,
    overriding any commercial/price content in the same turn) is decided by
    the conversation orchestration in azure_openai.py, not by this tool.
    """

    async def __call__(self, input: str = "") -> str:
        return json.dumps({"acknowledged": True})
