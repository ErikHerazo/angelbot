import re
from pathlib import Path
from typing import Optional


class InvalidDocumentUploadError(Exception):
    pass


def validate_document_upload(
    *,
    filename: str,
    content_type: Optional[str],
    size_bytes: int,
    allowed_extensions: set[str],
    allowed_mime_types: set[str],
    max_size_bytes: int,
) -> None:
    if not filename:
        raise InvalidDocumentUploadError("File must have a name")

    ext = Path(filename).suffix.lower()
    if ext not in allowed_extensions:
        raise InvalidDocumentUploadError(f"Extension not allowed: {ext}")

    if not content_type or content_type not in allowed_mime_types:
        raise InvalidDocumentUploadError("Invalid content type")

    if size_bytes == 0:
        raise InvalidDocumentUploadError("Empty file")

    if size_bytes > max_size_bytes:
        raise InvalidDocumentUploadError(f"File too large. Max {max_size_bytes} bytes")


def sanitize_blob_name(filename: str, prefix: Optional[str] = None) -> str:
    safe_name = filename.strip().replace(" ", "_")
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "", safe_name)

    if prefix:
        prefix = prefix if prefix.endswith("/") else f"{prefix}/"
        return f"{prefix}{safe_name}"

    return safe_name
