from fastapi import Header, HTTPException, status
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("UPLOAD_API_KEY")

def validate_upload_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida"
        )
