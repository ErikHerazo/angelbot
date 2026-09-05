from app.config import settings


def test_file_upload_limits_are_defined():
    assert ".pdf" in settings.ALLOWED_EXTENSIONS
    assert settings.MAX_FILE_SIZE_MB > 0
    assert "application/pdf" in settings.ALLOWED_MIME_TYPES


def test_language_display_names_include_core_languages():
    assert settings.LANGUAGE_DISPLAY_NAMES["es"] == "Español"
    assert settings.LANGUAGE_DISPLAY_NAMES["en"] == "Inglés"


def test_fallback_message_is_non_empty():
    assert settings.FALLBACK_MESSAGE
