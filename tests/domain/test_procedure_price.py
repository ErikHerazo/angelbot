from app.domain.value_objects.procedure_price import normalize_search_text


def test_lowercases_and_strips_accents():
    assert normalize_search_text("Liposucción de Abdomen") == "liposuccion de abdomen"


def test_removes_special_characters():
    assert normalize_search_text("¿Cuánto cuesta la rinoplastia?!") == "cuanto cuesta la rinoplastia"


def test_collapses_extra_whitespace():
    assert normalize_search_text("  aumento   de   pecho  ") == "aumento de pecho"


def test_empty_string_returns_empty():
    assert normalize_search_text("") == ""
    assert normalize_search_text(None) == ""
