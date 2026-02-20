import os
import logging
from app.core import constants
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, UploadFile, File
from app.services.cloud.azure.azure_blob import AzureBlobService
from fastapi import HTTPException
from fastapi import Form
from pathlib import Path
from app.web.utils import file_validators


router = APIRouter(
    prefix="/upload",
    tags=["upload"]
)

load_dotenv()
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=constants.WEB_DIR / "templates")

azure_service = AzureBlobService()

@router.get("/file", response_class=HTMLResponse)
async def render_home(request: Request):
    try:
        containers = azure_service.list_containers()

        return templates.TemplateResponse(
            "blob_upload.html",
            {
                "request": request,
                "containers": containers
            }
        )
    except Exception as e:
        logger.error(f"Error cargando contenedores: {e}")
        return templates.TemplateResponse(
            "blob_upload.html",
            {
                "request": request,
                "containers": []
            }
        )

@router.get("/containers")
async def list_containers():
    try:
        containers = azure_service.list_containers()
        return {"containers": containers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/to-azure")
async def upload_to_azure(
    file: UploadFile = File(...),
    container_name: str = Form(...)
):
    try:
        allowed = azure_service.list_containers()

        if container_name not in allowed:
            raise HTTPException(status_code=400, detail="Invalid container")

        file_validators.validate_extension(file)
        file_validators.validate_size(file)

        safe_name = file_validators.sanitize_filename(file.filename)

        azure_service.upload_blob_stream(
            container_name=container_name,
            blob_name=safe_name,
            file_obj=file.file
        )

        return {"filename": safe_name, "status": "ok"}

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Upload error")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    finally:
        await file.close()
