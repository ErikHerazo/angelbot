from app.application.use_cases.process_lead_submission import ProcessLeadSubmission
from app.domain.value_objects.lead_submission import LeadSubmission


class FakeConversationEngine:
    def __init__(self, *, answer=None, raise_exception=None):
        self._answer = answer
        self._raise_exception = raise_exception
        self.calls = []

    async def generate_reply(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise_exception:
            raise self._raise_exception
        return self._answer


def make_lead(reason="dolor de espalda", interest="liposuccion", lang="es"):
    return LeadSubmission(
        first_name="Ana",
        last_name="Perez",
        lang=lang,
        reason_for_appointment=reason,
        form_interest=interest,
    )


async def test_returns_no_intent_without_calling_engine():
    engine = FakeConversationEngine(answer="no debería llegar aquí")
    use_case = ProcessLeadSubmission(conversation_engine=engine)

    result = await use_case.execute(
        tenant_id="agb",
        session_id="sess-1",
        lead=make_lead(reason=None, interest=None),
    )

    assert result.success is False
    assert result.error_code == "NO_INTENT"
    assert engine.calls == []


async def test_returns_answer_on_success():
    engine = FakeConversationEngine(answer="claro, te explico")
    use_case = ProcessLeadSubmission(conversation_engine=engine)

    result = await use_case.execute(tenant_id="agb", session_id="sess-1", lead=make_lead())

    assert result.success is True
    assert result.answer == "claro, te explico"
    assert engine.calls[0]["channel"] == "flow"
    assert engine.calls[0]["visitor_language"] == "es"
    assert "dolor de espalda | liposuccion" in engine.calls[0]["user_question"]


async def test_returns_processing_error_when_engine_raises():
    engine = FakeConversationEngine(raise_exception=RuntimeError("boom"))
    use_case = ProcessLeadSubmission(conversation_engine=engine)

    result = await use_case.execute(tenant_id="agb", session_id="sess-1", lead=make_lead())

    assert result.success is False
    assert result.error_code == "PROCESSING_ERROR"
