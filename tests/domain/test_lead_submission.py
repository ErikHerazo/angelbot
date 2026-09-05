from app.domain.value_objects.lead_submission import LeadSubmission


def test_combined_intent_joins_both_fields():
    lead = LeadSubmission(
        first_name="Ana",
        last_name="Perez",
        lang="es",
        reason_for_appointment="dolor de espalda",
        form_interest="liposuccion",
    )

    assert lead.combined_intent == "dolor de espalda | liposuccion"


def test_combined_intent_with_only_one_field():
    lead = LeadSubmission(
        first_name="Ana",
        last_name="Perez",
        lang="es",
        reason_for_appointment=None,
        form_interest="liposuccion",
    )

    assert lead.combined_intent == "liposuccion"


def test_combined_intent_none_when_both_missing():
    lead = LeadSubmission(
        first_name="Ana",
        last_name="Perez",
        lang="es",
        reason_for_appointment=None,
        form_interest=None,
    )

    assert lead.combined_intent is None


def test_build_synthetic_question():
    lead = LeadSubmission(
        first_name="Ana",
        last_name="Perez",
        lang="en",
        reason_for_appointment="back pain",
        form_interest=None,
    )

    assert lead.build_synthetic_question() == "Motivo de consulta del paciente: back pain. Idioma: en."
