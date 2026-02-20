from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.core import constants
from uuid import uuid4


def validate_extension(file: UploadFile) -> None:
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="File must have a name")

        ext = Path(file.filename).suffix.lower()
        if ext not in constants.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Extension not allowed: {ext}"
            )

        if not file.content_type or file.content_type not in constants.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Invalid content type"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Extension validation error: {str(e)}"
        )

def validate_size(file: UploadFile) -> None:
    try:
        if not file.file:
            raise HTTPException(status_code=400, detail="Invalid file stream")

        original_position = file.file.tell()
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(original_position)

        if size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        max_bytes = constants.MAX_FILE_SIZE_MB * 1024 * 1024

        if size > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max {constants.MAX_FILE_SIZE_MB}MB"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Size validation error: {str(e)}"
        )

def sanitize_filename(filename: str) -> str:
    try:
        ext = Path(filename).suffix
        return f"{uuid4().hex}{ext}"
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Filename sanitize error: {str(e)}"
        )
    