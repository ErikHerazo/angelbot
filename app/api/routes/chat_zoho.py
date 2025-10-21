import uuid
import json
from fastapi import HTTPException
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi import Response
from app.services.langchain.langchain_openai import query_langchain_with_search
from app.services.cloud.azure.azure_openai import run_conversation_with_rag


router = APIRouter()

@router.head("/webhook", include_in_schema=False)
async def webhook_head():
    return Response(status_code=200)

@router.get("/webhook", include_in_schema=False)
async def webhook_get():
    return Response(status_code=200)

@router.post("/webhook")
async def zoho_bot_webhook(request: Request):
    body = await request.json()

    # 🔍 Print the complete JSON received to the console
    print("📩 Webhook recibido de Zoho:\n", json.dumps(body))

    user_question = body.get("message", {}).get("text") or \
                    body.get("question") or \
                    body.get("text")

    print("============ pregunta: ", user_question)
    if not user_question:
        welcome_payload = {
            "action": "reply",
            "replies": [
                {
                    "text": "👋 Hola.. soy Aesthea, el asistente virtual de Antiaging Group Barcelona, tu clínica de medicina y cirugía estética. Nuestro objetivo es que te sientas mejor."
                }
            ]
        }
        print("➡️ Respuesta de bienvenida enviada a Zoho:\n", json.dumps(welcome_payload, indent=2))
        return welcome_payload

    try:
        session_id = body.get("visitorId") or str(uuid.uuid4())
        print("===== Session id: ", session_id)
        answer = await run_conversation_with_rag(session_id, user_question)
        # answer = await query_langchain_with_search(user_question)
        print("respuesta: ", answer)
        print("respuesta: ", type(answer))
        response_payload = {
            "action":"reply",
            "replies": [
                {
                    "text": answer
                }
            ]
        }
        print("Respuesta enviada a Zoho:\n", json.dumps(response_payload, indent=2))
        return JSONResponse(content=response_payload, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    