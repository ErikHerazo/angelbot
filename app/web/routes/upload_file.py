import os
import logging
from app.core import constants
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, UploadFile, File
from app.services.cloud.azure.azure_blob import AzureBlobService


router = APIRouter(
    prefix="/upload",
    tags=["upload"]
)

load_dotenv()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=constants.WEB_DIR / "templates")

container_name=os.getenv("AZURE_STORAGE_CONTAINER_NAME")

@router.get("/file", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse(
        "blob_upload.html",
        {"request": request}
    )

@router.post("/to-azure")
async def upload_to_azure(file: UploadFile = File(...)):
    try:
        azure_service = AzureBlobService()

        # Guardar temporalmente
        temp_path = constants.WEB_DIR / "uploads" / file.filename
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # Subir a Azure
        azure_service.upload_blob(
            container_name="mi-contenedor",
            blob_name=file.filename,
            file_path=temp_path
        )

        return {"filename": file.filename, "status": "ok"}

    except Exception as e:
        # Retornar siempre JSON
        return {"error": str(e)}
