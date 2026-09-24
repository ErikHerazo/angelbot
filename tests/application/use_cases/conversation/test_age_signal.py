from app.application.use_cases.conversation.age_signal import (
    age_reinforcement_note,
    extract_age_from_user_turn,
    extract_youngest_age,
    extract_youngest_age_from_history,
    has_price_intent,
)


def test_extract_youngest_age_finds_a_single_mention():
    assert extract_youngest_age("tengo 15 años") == 15


def test_extract_youngest_age_returns_none_when_no_age_mentioned():
    assert extract_youngest_age("cuanto cuesta una rinoplastia") is None


def test_extract_youngest_age_picks_the_youngest_across_multiple_texts():
    assert extract_youngest_age("tengo 34 años", "mi hija tiene 15 años") == 15


def test_extract_youngest_age_ignores_empty_or_none_texts():
    assert extract_youngest_age("", None, "tengo 20 años") == 20


def test_age_reinforcement_note_empty_when_age_is_none():
    assert age_reinforcement_note(None) == ""


def test_age_reinforcement_note_applies_minor_rule_under_16_without_blocking_other_topics():
    note = age_reinforcement_note(14)
    assert "paciente de 14 años" in note
    assert "otro tema o de otra persona" in note


def test_age_reinforcement_note_present_for_16_and_17():
    assert "16 años NO es menor de 16" in age_reinforcement_note(16)
    assert "17 años NO es menor de 16" in age_reinforcement_note(17)


def test_age_reinforcement_note_empty_for_adults():
    assert age_reinforcement_note(18) == ""
    assert age_reinforcement_note(40) == ""


def test_extract_age_from_user_turn_accepts_bare_number_after_age_question():
    assert extract_age_from_user_turn("14", "¿Qué edad tiene tu hija?") == 14
    assert extract_age_from_user_turn("tiene 14", "¿Me indicas su edad?") == 14


def test_extract_age_from_user_turn_ignores_bare_number_without_age_question():
    assert extract_age_from_user_turn("14", "¿Cuántas sesiones quieres?") is None
    assert extract_age_from_user_turn("14", None) is None


def test_extract_youngest_age_from_history_only_reads_user_messages():
    history = [
        {"role": "assistant", "content": "¿Qué edad tiene?"},
        {"role": "user", "content": "15"},
        {"role": "assistant", "content": "Dado que tiene 12 años..."},
    ]
    assert extract_youngest_age_from_history(history) == 15


def test_has_price_intent():
    assert has_price_intent("¿Y cuánto cuesta?")
    assert has_price_intent("precio del aumento de pecho")
    assert not has_price_intent("no es para mi hija, es para mi")
