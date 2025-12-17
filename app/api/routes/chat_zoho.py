import uuid
import asyncio
import logging

from fastapi.responses import HTMLResponse, Response
from fastapi import APIRouter, Request, HTTPException

from app.core import security
from app.services.chat.zoho_processor import process_message_async
from app.core import security


router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/zoho-test", include_in_schema=False)
async def zoho_test_page():
    with open("app/static/zoho_test.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@router.get("/authorization", include_in_schema=False)
async def webhook_head():
    return Response(status_code=200)

@router.head("/webhook", include_in_schema=False)
async def webhook_head2():
    return Response(status_code=200)

@router.get("/webhook", include_in_schema=False)
async def webhook_get():
    return Response(status_code=200)

# --- ENDPOINT PRINCIPAL ---
@router.post("/webhook")
async def zoho_bot_webhook(request: Request):
    # Validates RSA signature and caches the body
    await security.validate_zoho_webhook(request)
    
    body = await request.json()
    
    handler = body.get("handler")
    message = body.get("message") or {}
    visitor = body.get("visitor", {})
    request_id = body.get("request", {}).get("id")
    user_question = message.get("text") or visitor.get("question")

    logger.info(
        "Zoho webhook received",
        extra={
            "handler": handler,
            "request_id": request_id,
        },
    )
    
    if handler == "trigger":
        welcome_payload = {
            "action": "reply",
            "replies": [
                {
                    "text": "👋 Hola.. soy Aesthea, el asistente virtual de Antiaging Group Barcelona, tu clínica de medicina y cirugía estética. Nuestro objetivo es que te sientas mejor."
                }
            ]
        }
        return welcome_payload

    try:
        session_id = body.get("visitor", {}).get("visitor_id")
        if not session_id:
            session_id = str(uuid.uuid4())

        if handler == "message":
            logger.info(
                "Message webhook received",
                extra={
                    "handler": handler,
                    "zoho_message": message,
                },
            )
            payload = {
                "action" : "pending",
                "replies" : ["estoy procesando tu solicitud..."]
            }

            # ✔️ Ejecutar tarea asincrónica después del return
            asyncio.create_task(
                process_message_async(
                    request_id, session_id,
                    user_question
                )
            )
            return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    