import os
import base64
import logging
import binascii

from dotenv import load_dotenv

from threading import Lock

from fastapi import Request, Header, HTTPException, status

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature


load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("UPLOAD_API_KEY")
API_KEY_OPENAI = os.getenv("AZURE_OPENAI_API_KEY_MAIN")

_PUBLIC_KEY = None
_PUBLIC_KEY_LOCK = Lock()

def _get_zoho_public_key():
    global _PUBLIC_KEY
    if _PUBLIC_KEY is None:
        with _PUBLIC_KEY_LOCK:
            if _PUBLIC_KEY is None:  # double-check
                raw = os.getenv("SIGNATURE_WEBHOOK_ZOHOSALESIQ")
                if not raw:
                    raise RuntimeError("Missing SIGNATURE_WEBHOOK_ZOHOSALESIQ env var")
                clean = raw.replace("\\n", "\n")
                _PUBLIC_KEY = serialization.load_pem_public_key(clean.encode())
    return _PUBLIC_KEY

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

def check_zoho_rsa_signature(signature: str, payload: bytes) -> bool:
    try:
        public_key = _get_zoho_public_key()

        try:
            signature_bytes = base64.b64decode(signature, validate=True)
        except (binascii.Error, ValueError):
            logger.debug("Invalid base64 signature")
            return False

        public_key.verify(
            signature_bytes,
            payload,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True

    except InvalidSignature:
        logger.debug("Invalid Zoho RSA signature")
        return False
    except Exception:
        logger.exception("Unexpected error verifying Zoho RSA signature")
        return False

async def validate_zoho_webhook(request: Request) -> bytes:
    signature_b64 = request.headers.get("x-siqsignature")

    if not signature_b64:
        raise HTTPException(
            status_code=400,
            detail="Missing header x-siqsignature"
        )

    body_bytes = await request.body()
    logger.info("x-siqsignature present=%s", bool(signature_b64))
    logger.info("x-siqsignature raw=%s", signature_b64)
    if not check_zoho_rsa_signature(signature_b64, body_bytes):
        raise HTTPException(
            status_code=403,
            detail="Invalid signature"
        )
    
    logger.info("✅ Zoho webhook RSA signature VALIDATED successfully")

    # ✅ REINYECTAR el body para que request.json() funcione
    async def receive():
        return {"type": "http.request", "body": body_bytes}

    request._receive = receive

    logger.info("Zoho webhook signature validated")
    return body_bytes
