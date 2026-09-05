from app.application.use_cases.process_lead_submission import ProcessLeadSubmission
from app.domain.value_objects.lead_submission import LeadSubmission


class ZohoFlowLeadHandler:
    """Formats ProcessLeadSubmission's result as the JSON body Zoho Flow
    expects synchronously -- same 3 response shapes as the legacy
    process_zoho_flow_lead (success / NO_INTENT / PROCESSING_ERROR),
    including its `source: "flow"` vs `source: "zoho_flow"` inconsistency
    between the success and error branches -- preserved as-is, not
    "fixed" unasked.
    """

    def __init__(self, *, use_case: ProcessLeadSubmission, tenant_id: str):
        self._use_case = use_case
        self._tenant_id = tenant_id

    async def handle(self, *, request_id: str, session_id: str, lead_data: dict) -> dict:
        first_name = lead_data.get("first_name", "")
        last_name = lead_data.get("last_name", "")
        lang = lead_data.get("lang", "es")
        reason = lead_data.get("motivo_de_la_cita")
        interest = lead_data.get("interes_formulario")

        lead = LeadSubmission(
            first_name=first_name,
            last_name=last_name,
            lang=lang,
            reason_for_appointment=reason,
            form_interest=interest,
        )

        result = await self._use_case.execute(
            tenant_id=self._tenant_id,
            session_id=session_id,
            lead=lead,
        )

        if result.success:
            return {
                "success": True,
                "response": result.answer,
                "intent": {"reason": reason, "interest": interest},
                "entities": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "lang": lang,
                },
                "meta": {
                    "request_id": request_id,
                    "session_id": session_id,
                    "source": "flow",
                },
                "error": None,
            }

        entities = (
            {"first_name": first_name, "last_name": last_name}
            if result.error_code == "NO_INTENT"
            else {}
        )

        return {
            "success": False,
            "response": None,
            "intent": None,
            "entities": entities,
            "meta": {
                "request_id": request_id,
                "session_id": session_id,
                "source": "zoho_flow",
            },
            "error": {"code": result.error_code, "message": result.error_message},
        }
