import json

from app.application.use_cases.lookup_procedure_price import LookupProcedurePrice

NO_QUERY_MESSAGE = "No se proporcionó un nombre de cirugía o tratamiento válido."
NOT_FOUND_MESSAGE = "Lo siento, ese tratamiento no se realiza en nuestra clínica actualmente."
FOUND_MESSAGE = (
    "Los precios indicados son aproximados y estan sujetos a cambios tras la "
    "valoracion medica especializada. "
)
REFERENCE_NOTE = "💡 Los precios del dataset son referenciales y pueden variar según el caso clínico."


class LookupProcedurePriceTool:
    """Exposes LookupProcedurePrice as an LLM tool call -- same JSON response
    shape as the legacy `procedures_and_treatments_price_list` in
    azure_tools.py. Async, same tool-dispatch caveat as
    CheckBusinessAvailabilityTool: not wired into the live (synchronous)
    azure_openai.py loop yet.
    """

    def __init__(self, *, use_case: LookupProcedurePrice, tenant_id: str):
        self._use_case = use_case
        self._tenant_id = tenant_id

    async def __call__(self, name_surgery_or_treatment: str) -> str:
        if not name_surgery_or_treatment or not name_surgery_or_treatment.strip():
            return json.dumps({
                "found": False,
                "results": [],
                "mensaje": NO_QUERY_MESSAGE,
                "nota": REFERENCE_NOTE,
            })

        results = await self._use_case.execute(self._tenant_id, name_surgery_or_treatment)

        if not results:
            return json.dumps({
                "found": False,
                "results": [],
                "mensaje": NOT_FOUND_MESSAGE,
                "nota": REFERENCE_NOTE,
            })

        return json.dumps({
            "found": True,
            "results": [
                {
                    "procedure_name": r.procedure_name,
                    "price_range": r.price_range,
                    "type_of_currency": r.currency,
                }
                for r in results
            ],
            "message": FOUND_MESSAGE,
        }, indent=2)
