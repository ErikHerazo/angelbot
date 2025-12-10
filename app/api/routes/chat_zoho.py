import asyncio
import uuid
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, Response
from app.services.cloud.azure.azure_openai import run_conversation_with_rag

router = APIRouter()

ZOHO_ACCESS_TOKEN = "1000.71691cecbb6712c6a66c3d0134b77435.0492069a0a983e05ef8691846d52fe2b"
SCREENNAME = "antiaginggroup"
ZOHOSALESIQ_SERVER_URI = "salesiq.zoho.eu"


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

# ---------------------------------------------------------------------
# ✔️ Nueva función para enviar la respuesta final vía API callback/response
# ---------------------------------------------------------------------
async def send_progress_update(request_id: str):
    """Envía un mensaje de 'progreso' para extender el tiempo de espera de Zoho."""

    url = f"https://{ZOHOSALESIQ_SERVER_URI}/api/v2/{SCREENNAME}/callbacks/{request_id}/progress"
    
    payload = {
        "text": "Just a few more seconds.."
    }
    
    headers = {
        "Authorization": f"Zoho-oauthtoken {ZOHO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        
        if resp.status_code not in (200, 204):
            print(f"ERROR PROGRESS", resp.status_code, resp.text)
            raise HTTPException(status_code=500, detail="Progress Failed")

async def send_final_response(request_id: str, answer_text: str):
    """Envia la respuesta final a Zoho para completar la acción pendiente."""
    url = f"https://{ZOHOSALESIQ_SERVER_URI}/api/v2/{SCREENNAME}/callbacks/{request_id}/response"

    payload = {
        "action" : "reply",
        "replies" : [
            {
            "type": "text",
            "text": answer_text,
            }
        ]
    }
    headers = {
        "Authorization": f"Zoho-oauthtoken {ZOHO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"=== Enviando respuesta final a Zoho para request_id: {request_id}")
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            print(f"ERROR al enviar mensaje ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

# --- ENDPOINT PRINCIPAL ---
@router.post("/webhook")
async def zoho_bot_webhook(request: Request):
    body = await request.json()
    
    handler = body.get("handler")
    message = body.get("message") or {}
    visitor = body.get("visitor", {})
    request_id = body.get("request", {}).get("id")
    user_question = message.get("text") or visitor.get("question")

    print(f"========== BODY: {body}")
    print(f"========== HANDLER: {handler}")
    print(f"========== REQUEST_ID: {request_id}")
    print(f"========== USER_QUESTION: {user_question}")
    
    if handler == "trigger":
        welcome_payload = {
            "action": "reply",
            "replies": [
                {
                    "text": "👋 Hola.. soy Aesthea, el asistente virtual de Antiaging Group Barcelona, tu clínica de medicina y cirugía estética. Nuestro objetivo es que te sientas mejor."
                }
            ]
        }
        # print("➡️ Respuesta de bienvenida enviada a Zoho:\n", json.dumps(welcome_payload, indent=2))
        return welcome_payload

    try:
        session_id = body.get("visitorId") or str(uuid.uuid4())
        
        if handler == "message":
            payload = {
                "action" : "pending",
                "replies" : ["estoy procesando tu solicitud..."]
            }

            # await send_progress_update(request_id)
            return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))