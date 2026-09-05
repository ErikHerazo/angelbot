import pytest

from app.domain.value_objects.knowledge_document import (
    InvalidDocumentUploadError,
    sanitize_blob_name,
    validate_document_upload,
)

ALLOWED_EXTENSIONS = {".pdf", ".csv"}
ALLOWED_MIME_TYPES = {"application/pdf", "text/csv"}
MAX_SIZE = 10 * 1024 * 1024


def validate(**overrides):
    defaults = dict(
        filename="precios.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        allowed_extensions=ALLOWED_EXTENSIONS,
        allowed_mime_types=ALLOWED_MIME_TYPES,
        max_size_bytes=MAX_SIZE,
    )
    defaults.update(overrides)
    validate_document_upload(**defaults)


def test_valid_upload_does_not_raise():
    validate()  # no exception


def test_rejects_missing_filename():
    with pytest.raises(InvalidDocumentUploadError):
        validate(filename="")


def test_rejects_disallowed_extension():
    with pytest.raises(InvalidDocumentUploadError):
        validate(filename="malware.exe")


def test_rejects_disallowed_mime_type():
    with pytest.raises(InvalidDocumentUploadError):
        validate(content_type="application/octet-stream")


def test_rejects_empty_file():
    with pytest.raises(InvalidDocumentUploadError):
        validate(size_bytes=0)


def test_rejects_file_too_large():
    with pytest.raises(InvalidDocumentUploadError):
        validate(size_bytes=MAX_SIZE + 1)


def test_sanitize_blob_name_replaces_spaces_and_strips_special_chars():
    assert sanitize_blob_name("lista de precios (2026)!.pdf") == "lista_de_precios_2026.pdf"


def test_sanitize_blob_name_with_prefix():
    assert sanitize_blob_name("precios.pdf", prefix="clinica-agb") == "clinica-agb/precios.pdf"


def test_sanitize_blob_name_prefix_already_has_trailing_slash():
    assert sanitize_blob_name("precios.pdf", prefix="clinica-agb/") == "clinica-agb/precios.pdf"
