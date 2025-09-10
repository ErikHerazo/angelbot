import json
from app.core import security
from fastapi import HTTPException
from fastapi import APIRouter, Request, Depends
from app.services.langchain.langchain_openai import query_langchain_with_search


router = APIRouter()

@router.get("/webhook")
async def webhook_head():
    return {}

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
                },
                {
                    "text": "Antes de iniciar.., ¿podrías darme tu nombre completo y tu dirección de email?"
                }
            ]
        }
        print("➡️ Respuesta de bienvenida enviada a Zoho:\n", json.dumps(welcome_payload, indent=2))
        return welcome_payload

    try:
        # Usa Azure o LangChain dependiendo de lo que quieras
        # answer = query_azure_openai_with_search(user_question)
        answer = await query_langchain_with_search(user_question)
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
        return response_payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
