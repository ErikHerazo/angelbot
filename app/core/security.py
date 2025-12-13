import os
import base64
from dotenv import load_dotenv

from fastapi import Header, HTTPException, status

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


load_dotenv()

API_KEY = os.getenv("UPLOAD_API_KEY")
API_KEY_OPENAI = os.getenv("AZURE_OPENAI_API_KEY_MAIN")

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
    """
    Verifica la firma RSA de Zoho usando la clave pública almacenada en Azure Key Vault.

    :param signature: Firma enviada por Zoho en Base64.
    :param payload: Datos originales (payload) que Zoho firmó, en bytes.
    :return: True si la firma es válida, False si no lo es.
    """
    SIGNATURE_WEBHOOK_ZOHOSALESIQ=os.getenv("SIGNATURE_WEBHOOK_ZOHOSALESIQ")
    signature_webhook_zohosalesiq = SIGNATURE_WEBHOOK_ZOHOSALESIQ
    clean_key = signature_webhook_zohosalesiq.replace("\\n", "\n")
    
    public_key = serialization.load_pem_public_key(
        clean_key.encode(),
    )
    print(f"========== public_key: {public_key}")

    # Decodificar la firma de Base64
    signature_bytes = base64.b64decode(signature)
    print(f"========== signature_bytes: {signature_bytes}")

    try:
        # Verificar la firma
        public_key.verify(
            signature_bytes,
            payload,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False
    