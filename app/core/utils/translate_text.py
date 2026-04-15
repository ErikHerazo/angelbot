import httpx, uuid, os
from app.core import constants
from dotenv import load_dotenv


load_dotenv()

AZURE_TRANSLATOR_API_KEY = os.getenv("AZURE_TRANSLATOR_API_KEY")
AZURE_TRANSLATOR_ENDPOINT = constants.AZURE_TRANSLATOR_ENDPOINT
AZURE_TRANSLATOR_LOCATION = constants.AZURE_TRANSLATOR_LOCATION
AZURE_TRANSLATOR_PATH = constants.AZURE_TRANSLATOR_PATH

async def translate_text(text: str, from_lang: str, to_lang: str) -> str:
    # 🔹 1. Avoid empty text
    if not text:
        return text

    # 🔹 2. Avoid unnecessary translation
    if from_lang == to_lang:
        return text
    
    endpoint = AZURE_TRANSLATOR_ENDPOINT
    key = AZURE_TRANSLATOR_API_KEY
    location = AZURE_TRANSLATOR_LOCATION
    path = AZURE_TRANSLATOR_PATH

    constructed_url = endpoint + path
    
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": location,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4())
    }

    params = {
        "from": from_lang,
        "to": [to_lang,]
    }

    body = [{
        "text": text
    }]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                constructed_url,
                params=params,
                headers=headers,
                json=body
            )
            response.raise_for_status()

            data = response.json()
            return data[0]["translations"][0]["text"]

    except Exception as e:
        print(f"⚠️ Translation error: {e}")
        return text  # fallback seguro
    