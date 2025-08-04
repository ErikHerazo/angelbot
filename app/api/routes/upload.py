# app/api/routes/upload.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.cloud.azure.azure_blob import upload_file_to_blob


router = APIRouter()

@router.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        upload_file_to_blob(file.filename, contents)
        return {"documento": f"Archivo '{file.filename}' subido correctamente a Azure Blob"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
