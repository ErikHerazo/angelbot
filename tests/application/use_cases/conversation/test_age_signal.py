from app.application.use_cases.conversation.age_signal import (
    age_reinforcement_note,
    extract_youngest_age,
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


def test_age_reinforcement_note_empty_for_minors_under_16():
    assert age_reinforcement_note(12) == ""
    assert age_reinforcement_note(15) == ""


def test_age_reinforcement_note_present_for_16_and_17():
    assert "16 años NO es menor de 16" in age_reinforcement_note(16)
    assert "17 años NO es menor de 16" in age_reinforcement_note(17)


def test_age_reinforcement_note_empty_for_adults():
    assert age_reinforcement_note(18) == ""
    assert age_reinforcement_note(40) == ""
