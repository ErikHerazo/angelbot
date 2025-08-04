# app/api/routes/upload.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.cloud.azure.azure_blob import upload_file_to_blob
from app.core import security


router = APIRouter()

@router.post("/upload/", dependencies=[Depends(security.validate_upload_api_key)])
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        upload_file_to_blob(file.filename, contents)
        return {"documento": f"Archivo '{file.filename}' subido correctamente a Azure Blob"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
