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

# def is_customer_service_available(input: str = ""):
#     """
#     Indica si el personal de servicio al cliente está disponible actualmente en la clinica.
    
#     Retorna un string JSON con:
#       - available: True/False
#       - message: texto explicativo que el modelo puede usar.
#     """
#     # return test available=True
#     return json.dumps({
#         "available": False,
#         "message": "El servicio de atención al cliente no está disponible actualmente."
#     })

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

def save_user(name: str, email: str):
    """
    Inserta un nuevo registro en la tabla 'users' si no existe previamente.
    Retorna un string JSON con:
      - message: texto explicativo que el modelo o el frontend pueden usar.
    """

    # 🧹 Normalización básica
    name = name.strip().title() if name else ""
    email = email.strip().lower() if email else ""

    check_query = "SELECT COUNT(*) FROM users WHERE email = ?;"
    insert_query = "INSERT INTO users (name, email) VALUES (?, ?);"

    try:
        ensure_users_table()  # Asegura que la tabla exista

        with connection.get_connection() as conn:
            with conn.cursor() as cursor:
                # 🔍 Validar si el usuario ya existe
                cursor.execute(check_query, (email,))
                exists = cursor.fetchone()[0] > 0

                if exists:
                    logger.info(f"⚠️ Usuario existente: {email}")
                    return json.dumps({
                        "status": "already_exists",
                        "message": f"El correo '{email}' ya está registrado. Intente con otro o contacte soporte."
                    })

                # 🆕 Insertar nuevo usuario
                cursor.execute(insert_query, (name, email))
                conn.commit()

        logger.info(f"✅ Usuario registrado correctamente: {name} <{email}>")

        return json.dumps({
            "status": "created",
            "message": f"Usuario '{name}' con correo '{email}' registrado correctamente."
        })

    except Exception as error:
        logger.error(f"❌ Error al registrar usuario [{email}]: {error}")
        return json.dumps({
            "status": "error",
            "message": f"No se pudo registrar al usuario '{name}' con correo '{email}'. Error: {error}"
        })

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
    Busca coincidencias de procedimientos, tratamientos y cirugías en el archivo de precios almacenado en Azure Blob Storage.
    La búsqueda es insensible a mayúsculas, acentos, caracteres especiales y soporta:
      - Coincidencias parciales
      - Búsqueda por múltiples palabras sin importar el orden.
    Retorna un string JSON con los resultados y una nota aclaratoria indicando que los precios son referenciales.
    """
    results = []
    query_words = normalize_text(name_surgery_or_treatment).split()
    query_str = " ".join(query_words)

    if not query_words:
        return json.dumps({
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
        
        simplified ={
            "found": True,
            "results": [
                {
                    "procedure_name": doc.get("procedure_name", ""),
                    "price_range": doc.get("price_range_eur", ""),
                    "type_of_currency": "EUR"
                }
                for doc in results.get("value", [])
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
            "name": "save_user",
            "description": "Guarda la información de un usuario en la base de datos. "
                            "Utilízala cuando el usuario proporcione su nombre y correo electrónico "
                            "para registrarse, dejar sus datos de contacto o continuar una solicitud con un asesor. "
                            "La función crea la tabla 'users' si no existe y almacena el registro. "
                            "Devuelve un objeto JSON con el estado de la operación ('status') y un mensaje descriptivo ('message').",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Nombre del usuario. "
                        ),
                    },
                    "email": {
                        "type": "string",
                        "description": (
                            "Correo electronico del usuario, se usa para que un asesor de atencion al clinete contacte al usuario en horario disponible. "
                        ),
                    },
                },
                "required": ["name", "email"],
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
    }
]
