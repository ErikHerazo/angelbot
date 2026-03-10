import logging
from app.core import constants
from app.core.config import Settings
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, UploadFile, File
from app.services.cloud.azure.azure_blob import AzureBlobService
from fastapi import HTTPException
from fastapi import Form
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
                "containers": containers,
                "azure_client_id": Settings.AZURE_CLIENT_ID,
                "azure_tenant_id": Settings.AZURE_TENANT_ID
            }
        )
    except Exception as e:
        logger.error(f"Error loading containers: {e}")
        return templates.TemplateResponse(
            "blob_upload.html",
            {
                "request": request,
                "containers": [],
                "azure_client_id": Settings.AZURE_CLIENT_ID,
                "azure_tenant_id": Settings.AZURE_TENANT_ID
            }
        )

@router.get("/containers")
async def list_containers():
    try:
        containers = azure_service.list_containers()
        return {"containers": containers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/prefixes")
async def get_prefixes(
    container_name: str,
    parent_prefix: str | None = None
):
    try:
        # Validate that the container exists in the storage account
        allowed_containers = azure_service.list_containers()

        if container_name not in allowed_containers:
            raise HTTPException(
                status_code=400,
                detail="Invalid container"
            )

        # Retrieve virtual folder prefixes
        prefixes = azure_service.list_prefixes(
            container_name=container_name,
            parent_prefix=parent_prefix
        )

        return {
            "container": container_name,
            "parent_prefix": parent_prefix,
            "prefixes": prefixes
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Error retrieving prefixes")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve prefixes"
        )
    
@router.post("/to-azure")
async def upload_to_azure(
    file: UploadFile = File(...),
    container_name: str = Form(...),
    prefix: str = Form(None)
):
    try:
        allowed = azure_service.list_containers()

        if container_name not in allowed:
            raise HTTPException(status_code=400, detail="Invalid container")

        file_validators.validate_extension(file)
        file_validators.validate_size(file)

        blob_name = azure_service.upload_blob_stream(
            container_name=container_name,
            file=file,
            prefix=prefix
        )

        return {"filename": blob_name, "status": "ok"}

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Upload error")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    finally:
        await file.close()
