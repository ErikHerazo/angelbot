import json

from app.application.use_cases.check_business_availability import CheckBusinessAvailability


class CheckBusinessAvailabilityTool:
    """Exposes CheckBusinessAvailability as an LLM tool call -- same JSON
    response shape as the legacy `is_customer_service_available` in
    azure_tools.py (kept for the LLM's benefit, not a domain concern).

    Async, on purpose: the current azure_openai.py tool-dispatch loop calls
    tools synchronously, so wiring this in place of the legacy function
    needs that loop to support async tools first -- not done yet, tracked
    separately, out of scope for this piece.
    """

    def __init__(self, *, use_case: CheckBusinessAvailability, tenant_id: str):
        self._use_case = use_case
        self._tenant_id = tenant_id

    async def __call__(self, input: str = "") -> str:
        available = await self._use_case.execute(self._tenant_id)

        message = (
            "Servicio de atencion al cliente disponible."
            if available
            else "Servicio de atencion al cliente no disponible."
        )

        return json.dumps({"available": available, "message": message})
