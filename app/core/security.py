import os
from dotenv import load_dotenv
from fastapi import Header, HTTPException, status

load_dotenv()

API_KEY = os.getenv("UPLOAD_API_KEY")
API_KEY_OPENAI = os.getenv("AZURE_OPENAI_API_KEY_MAIN")
ZOHO_WEBHOOK_API_KEY=os.getenv("ZOHO_WEBHOOK_API_KEY")

def validate_upload_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida"
        )
    
def validate_upload_api_key_openai(x_api_key: str = Header(...)):
    if x_api_key != API_KEY_OPENAI:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida"
        )
    