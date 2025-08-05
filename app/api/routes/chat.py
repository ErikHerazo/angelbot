from app.core import security
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.cloud.azure.azure_openai import query_azure_openai_with_search


router = APIRouter()

class ChatRequest(BaseModel):
    question: str

@router.post("/chat", dependencies=[Depends(security.validate_upload_api_key_openai)])
def chat_with_openai(request: ChatRequest):
    try:
        answer = query_azure_openai_with_search(request.question)
        return {"response": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
