from fastapi import APIRouter, Request
from fastapi import HTTPException
from app.services.langchain.langchain_openai import query_langchain_with_search


router = APIRouter()

@router.post("/webhook")
async def zoho_bot_webhook(request: Request):
    body = await request.json()
    user_question = body.get("question") or body.get("message")

    if not user_question:
        raise HTTPException(status_code=400, detail="No question provided.")

    try:
        # Usa Azure o LangChain dependiendo de lo que quieras
        # answer = query_azure_openai_with_search(user_question)
        answer = await query_langchain_with_search(user_question)
        return {"reply": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
