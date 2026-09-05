from app.adapters.inbound.zoho.flow_lead_handler import ZohoFlowLeadHandler
from app.application.use_cases.process_lead_submission import LeadSubmissionResult


class FakeUseCase:
    def __init__(self, result):
        self._result = result

    async def execute(self, *, tenant_id, session_id, lead):
        return self._result


async def test_success_response_shape():
    handler = ZohoFlowLeadHandler(
        use_case=FakeUseCase(LeadSubmissionResult(success=True, answer="respuesta")),
        tenant_id="agb",
    )

    result = await handler.handle(
        request_id="req-1",
        session_id="sess-1",
        lead_data={
            "first_name": "Ana",
            "last_name": "Perez",
            "lang": "es",
            "motivo_de_la_cita": "dolor",
            "interes_formulario": "lipo",
        },
    )

    assert result == {
        "success": True,
        "response": "respuesta",
        "intent": {"reason": "dolor", "interest": "lipo"},
        "entities": {"first_name": "Ana", "last_name": "Perez", "lang": "es"},
        "meta": {"request_id": "req-1", "session_id": "sess-1", "source": "flow"},
        "error": None,
    }


async def test_no_intent_response_shape():
    handler = ZohoFlowLeadHandler(
        use_case=FakeUseCase(
            LeadSubmissionResult(success=False, error_code="NO_INTENT", error_message="No intent was found in the form")
        ),
        tenant_id="agb",
    )

    result = await handler.handle(
        request_id="req-1",
        session_id="sess-1",
        lead_data={"first_name": "Ana", "last_name": "Perez"},
    )

    assert result["success"] is False
    assert result["entities"] == {"first_name": "Ana", "last_name": "Perez"}
    assert result["meta"]["source"] == "zoho_flow"
    assert result["error"] == {"code": "NO_INTENT", "message": "No intent was found in the form"}


async def test_processing_error_response_shape():
    handler = ZohoFlowLeadHandler(
        use_case=FakeUseCase(
            LeadSubmissionResult(
                success=False,
                error_code="PROCESSING_ERROR",
                error_message="An error occurred while processing the request.",
            )
        ),
        tenant_id="agb",
    )

    result = await handler.handle(
        request_id="req-1",
        session_id="sess-1",
        lead_data={"first_name": "Ana", "last_name": "Perez", "motivo_de_la_cita": "dolor"},
    )

    assert result["success"] is False
    assert result["entities"] == {}
    assert result["meta"]["source"] == "zoho_flow"
