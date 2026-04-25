import httpx
import uuid
import os
from dotenv import load_dotenv
from app.core import constants


load_dotenv()

AZURE_TRANSLATOR_API_KEY = os.getenv("AZURE_TRANSLATOR_API_KEY")
AZURE_DETECT_ENDPOINT = constants.AZURE_DETECT_ENDPOINT
AZURE_DETECT_LOCATION = constants.AZURE_DETECT_LOCATION
AZURE_DETECT_PATH = constants.AZURE_DETECT_PATH


async def detect_language_azure(text: str) -> str | None:
    # 🔹 1. Validación básica
    if not text or not text.strip():
        return None

    url = f"{AZURE_DETECT_ENDPOINT}{AZURE_DETECT_PATH}"

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_API_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_DETECT_LOCATION,
        "Content-Type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }

    body = [{"text": text}]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()

            data = response.json()

            # 🔹 Validar estructura de respuesta
            if not data or "language" not in data[0]:
                return None

            # 🔹 Obtener idioma
            lang = data[0]["language"]

            # 🔹 Normalizar (ej: "es-ES" → "es")
            lang = lang.split("-")[0].lower()

            print("🌐 idioma detectado (raw):", lang)

            return lang  # 🔥 IMPORTANTE: no filtrar aquí

    except httpx.TimeoutException:
        print("⚠️ Azure detect timeout")
        return None

    except httpx.HTTPStatusError as e:
        print(f"⚠️ Azure detect HTTP error: {e.response.status_code}")
        return None

    except Exception as e:
        print(f"⚠️ Azure detect error: {e}")
        return None
    