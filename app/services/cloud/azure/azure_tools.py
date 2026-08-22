import os
import re
import json
import holidays
import requests
import unicodedata
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from datetime import datetime, time
from app.services.db import connection
from app.core.logging_config import logger


load_dotenv()

# Obtener hora actual de España
def get_current_time_spain() -> datetime:
    madrid_tz = ZoneInfo("Europe/Madrid")
    return datetime.now(madrid_tz)

def is_customer_service_available(input: str=""):
    now = get_current_time_spain()
    weekday = now.weekday()   # 0=Lunes, 6=Domingo
    current_time = now.time()
    today = now.date()

    es_holidays = holidays.Spain(years=now.year)

    # Día no laboral
    if weekday == 6 or today in es_holidays:
        return json.dumps({
            "available": False,
            "message": (
                "Servicio de atencion al cliente no disponible."
            )
        })

    # Lunes a jueves
    if 0 <= weekday <= 3:
        if (
            time(10, 30) <= current_time <= time(14, 0)
            or time(15, 30) <= current_time <= time(19, 0)
        ):
            return json.dumps({
                "available": True,
                "message": (
                    "Servicio de atencion al cliente disponible. "
                )
            })

    # Viernes
    if weekday == 4:
        if time(10, 30) <= current_time <= time(14, 0):
            return json.dumps({
                "available": True,
                "message": (
                    "Servicio de atencion al cliente disponible. "
                )
            })

    return json.dumps({
        "available": False,
        "message": (
            "Servicio de atencion al cliente no disponible. "
        )
    })

def ensure_users_table():
    """
    Ensures that the 'users' table exists in the database.
    If it does not exist, it will be created.

    Table schema:
        id    INT PRIMARY KEY IDENTITY(1,1)
        name  NVARCHAR(255) NOT NULL
        email NVARCHAR(255) UNIQUE NOT NULL
    """
    create_table_query = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
    CREATE TABLE users (
        id INT PRIMARY KEY IDENTITY(1,1),
        name NVARCHAR(255) NOT NULL,
        email NVARCHAR(255) UNIQUE NOT NULL
    );
    """

    try:
        with connection.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
    except Exception as error:
        print(f"⚠️ Failed to ensure 'users' table exists: {error}")

def normalize_text(text: str) -> str:
    """
    Normaliza un texto para búsquedas:
    - Convierte a minúsculas
    - Quita acentos y diacríticos
    - Elimina caracteres no alfanuméricos (excepto espacios)
    """
    if not text:
        return ""
    
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def procedures_and_treatments_price_list(name_surgery_or_treatment: str) -> str:
    """
    Searches for matching procedures, treatments, and surgeries in the pricing file stored in Azure Blob Storage.
    The search is case-insensitive, unaffected by accents or special characters, and supports:
    - Partial matches
    - Multi-word searches regardless of order.
    Returns a JSON string with the results and a note indicating that the prices are for reference only.
    """

    query_words = normalize_text(name_surgery_or_treatment).split()
    query_str = " ".join(query_words)

    if not query_words:
        return json.dumps({
            "found": False,
            "results": [],
            "mensaje": "No se proporcionó un nombre de cirugía o tratamiento válido.",
            "nota": "💡 Los precios del dataset son valores referenciales y pueden variar según el caso clínico."
        })
    
    price_list_index=os.getenv("AZURE_AI_SEARCH_PRICE_LIST_INDEX")
    azure_ai_search_api_key=os.getenv("AZURE_AI_SEARCH_API_KEY")
    
    try:
        url = f"https://agb-search.search.windows.net/indexes/{price_list_index}/docs/search?api-version=2025-11-01-preview"
    
        headers = {
            "Content-Type": "application/json",
            "api-key": azure_ai_search_api_key
        }
    
        payload = {
            "search": query_str,
            "count": True
        }
    
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Search error: {response.status_code} - {response.text}")
        
        results = response.json()
        docs = results.get("value", [])

        # ✅ Si no se recuperaron documentos, mensaje por defecto
        if len(docs) == 0:
            return json.dumps({
                "found": False,
                "results": [],
                "mensaje": "Lo siento, ese tratamiento no se realiza en nuestra clínica actualmente.",
                "nota": "💡 Los precios del dataset son referenciales y pueden variar según el caso clínico."
            })
        
        simplified ={
            "found": True,
            "results": [
                {
                    "procedure_name": doc.get("procedure_name", ""),
                    "price_range": doc.get("price_range_eur", ""),
                    "type_of_currency": "EUR"
                }
                for doc in docs
            ],
            "message": "Los precios indicados son aproximados y estan sujetos a cambios tras la valoracion medica especializada. "
        }
        return json.dumps(simplified, indent=2)
    
    except Exception as e:
        logger.error(f"❌ Error en procedures_and_treatments_price_list: {e}")
        return json.dumps({
            "error": f"Ocurrió un error leyendo el CSV desde Azure Blob: {str(e)}",
            "nota": "💡 Los precios del dataset son referenciales y pueden variar."
        })

def flag_revision_or_reintervention_price_request(input: str = "") -> str:
    """
    No busca ni calcula ningún precio. Es una señal: el LLM la llama cuando
    detecta que el usuario ya se sometió antes a una cirugía o tratamiento
    en la misma zona y ahora pide precio para una revisión/reintervención.
    El código (azure_openai.py) usa esta llamada para responder de forma
    determinista en vez de dejar que el LLM improvise un precio, ya que el
    catálogo de precios solo tiene el valor de la intervención de primera
    vez, que no aplica a una revisión.
    """
    return json.dumps({"acknowledged": True})


tools = [
    {
        "type": "function",
        "function": {
            "name": "is_customer_service_available",
            "description": "Comprueba si el servicio de atención al cliente está disponible actualmente en España. "
                            "Utilízala cuando el usuario pregunte si puede ser atendido por un asesor, "
                            "si el usuario quiere reservar una cita, "
                            "si hay soporte disponible, o si el horario de atención está activo. "
                            "Devuelve True si el servicio está disponible en este momento, de lo contrario False.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": (
                            "Texto opcional proporcionado por el usuario. "
                            "Puede incluir su consulta o contexto, aunque no es necesario "
                            "para determinar la disponibilidad del servicio."
                        ),
                    },
                },
                "required": ["input"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "procedures_and_treatments_price_list",
            "description":  "Busca coincidencias de procedimientos, tratamientos y cirugías en el archivo de precios "
                            "almacenado en Azure Blob Storage. La búsqueda es insensible a mayúsculas, acentos y caracteres especiales, "
                            "y soporta coincidencias parciales y búsqueda por múltiples palabras sin importar el orden. "
                            "Devuelve un string JSON con los resultados encontrados o un mensaje explicativo si no hay coincidencias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_surgery_or_treatment": {
                        "type": "string",
                        "description": (
                            "Nombre de la cirugía o tratamiento que se desea buscar en la lista de precios. "
                            "Puede ser parcial o contener varias palabras."
                        ),
                    },
                },
                "required": ["name_surgery_or_treatment"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flag_revision_or_reintervention_price_request",
            "description": "Llama a esta función, EN VEZ DE `procedures_and_treatments_price_list`, cuando "
                            "el usuario indica que ya se sometió antes a una cirugía o tratamiento en la misma "
                            "zona (por ejemplo: ya me operé, cirugía previa, segunda operación, reintervención, "
                            "revisión, no quedé bien, quiero corregir el resultado, quiero un retoque) Y además "
                            "está pidiendo el precio, costo, tarifa o presupuesto de esa revisión/reintervención. "
                            "No inventes ni utilices el precio de la cirugía de primera vez para este caso.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Texto del usuario que motivó la detección de reintervención con pregunta de precio.",
                    },
                },
                "required": ["input"],
            },
        }
    }
]
