import os
import uuid
import asyncio
import logging

from dotenv import load_dotenv

from fastapi.responses import HTMLResponse, Response
from fastapi import APIRouter, Request, HTTPException

from app.core import security
from app.services.cloud.azure.azure_openai import run_conversation_with_rag
from app.services.zoho.client import ZohoClient


router = APIRouter()

load_dotenv()

logger = logging.getLogger(__name__)

ZOHO_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN")

zoho_client = ZohoClient(access_token=ZOHO_ACCESS_TOKEN)

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

async def process_message_async(request_id: str, session_id: str, user_question: str):
    try:
        logger.info(
            "Processing Zoho message",
            extra={
                "request_id": request_id,
                "session_id": session_id,
            },
        )
        # 1) Enviar progreso
        await zoho_client.send_progress_update(request_id=request_id)

        # 2) Generar respuesta LLM (tu RAG)
        answer = await run_conversation_with_rag(session_id, user_question)

        # 3) Enviar respuesta final
        await zoho_client.send_final_response(request_id=request_id, answer_text=answer)

        logger.info(
            "Zoho response completed",
            extra={"request_id": request_id},
        )
    except Exception as e:
        logger.exception(
            "Zoho async processing failed",
            extra={"request_id": request_id},
        )

# --- ENDPOINT PRINCIPAL ---
@router.post("/webhook")
async def zoho_bot_webhook(request: Request):
    signature_b64 = request.headers.get("x-siqsignature")
    body_bytes = await request.body()

    print(f"========== SIGNATURE: {signature_b64}")
    print(f"========== Zoho Full Payload: {body_bytes}")

    if not signature_b64:
        raise HTTPException(400, detail="Falta header x-siqsignature")

    # Verificar la firma
    if not security.check_zoho_rsa_signature(signature_b64, body_bytes):
        raise HTTPException(403, detail="Firma inválida")
    print("================= SUCCESSFUL RSA SIGNATURE VALIDATION ========================")
    
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
    