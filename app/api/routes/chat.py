from app.core import security
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.cloud.azure.azure_openai import run_conversation


router = APIRouter()

class ChatRequest(BaseModel):
    question: str

@router.post("/chat", dependencies=[Depends(security.validate_upload_api_key_openai)])
def chat_with_openai(request: ChatRequest):
    try:
        answer = run_conversation(request.question)
        return {"response": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
