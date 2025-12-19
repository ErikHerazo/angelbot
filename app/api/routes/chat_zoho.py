import uuid
import asyncio
import logging

from fastapi.responses import HTMLResponse, Response
from fastapi import APIRouter, Request, HTTPException

from app.core import security
from app.services.chat.zoho_payload import parse_zoho_payload
from app.services.chat.zoho_processor import process_message_async

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

# --- MAIN ENDPOINT ---
@router.post("/webhook")
async def zoho_bot_webhook(request: Request):
    # Validates RSA signature and caches the body
    await security.validate_zoho_webhook(request)
    
    body = await request.json()
    zoho_message = parse_zoho_payload(body=body)

    logger.info(
        "Zoho webhook received",
        extra={
            "handler": zoho_message.handler,
            "request_id": zoho_message.request_id,
        },
    )
    
    if zoho_message.handler == "trigger":
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
        session_id = zoho_message.session_id or str(uuid.uuid4())

        if zoho_message.handler == "message":
            logger.info(
                "Message webhook received",
                extra={
                    "handler": zoho_message.handler,
                    "has_question": bool(zoho_message.user_question),
                },
            )
            payload = {
                "action" : "pending",
                "replies" : ["I am processing your request..."]
            }

            # ✔️ Execute asynchronous task after return
            asyncio.create_task(
                process_message_async(
                    request_id=zoho_message.request_id,
                    session_id=session_id,
                    user_question=zoho_message.user_question
                )
            )
            return payload
    except Exception as e:
        logger.exception(
            "Zoho webhook failed",
            extra={"request_id": zoho_message.request_id},
        )
        raise HTTPException(status_code=500, detail=str(e))
    