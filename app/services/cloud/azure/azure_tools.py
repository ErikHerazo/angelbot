import os
import re
import json
import httpx
import holidays
import unicodedata
from typing import Optional
from zoneinfo import ZoneInfo
from app.core import constants
from fastapi import HTTPException
from datetime import datetime, time
from app.services.db import connection
from app.core.logging_config import logger
from app.services.cloud.azure.azure_blob import AzureBlobService

# Obtener hora actual de España
def get_current_time_spain() -> datetime:
    madrid_tz = ZoneInfo("Europe/Madrid")
    return datetime.now(madrid_tz)

def is_customer_service_available(input: str = ""):
    now = get_current_time_spain()
    dia_semana = now.weekday()  # Lunes=0, Domingo=6
    es_holidays = holidays.Spain(years=now.year)

    # Domingo o festivo
    if dia_semana == 6 or now.date() in es_holidays:
        return json.dumps({
            "message": "El servicio de atención al cliente no está disponible hoy (domingo o festivo)."
        })

    # Horario laboral
    message = "El servicio de atención al cliente no está disponible en este momento."

    if 0 <= dia_semana <= 4:
        if time(8, 0) <= now.time() <= time(12, 0) or time(14, 0) <= now.time() <= time(18, 0):
            message = "El servicio de atención al cliente está disponible actualmente."
    elif dia_semana == 5:
        if time(8, 0) <= now.time() <= time(12, 0):
            message = "El servicio de atención al cliente está disponible actualmente."

    return json.dumps({"message": message})


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

    resultados = []
    query_words = normalize_text(name_surgery_or_treatment).split()

    if not query_words:
        return json.dumps({
            "mensaje": "No se proporcionó un nombre de cirugía o tratamiento válido.",
            "nota": "💡 Los precios del dataset son valores referenciales y pueden variar según el caso clínico."
        })

    try:
        # Inicializamos el servicio de Blob
        blob_service = AzureBlobService()

        # Leemos el CSV remoto
        df = blob_service.read_csv_from_blob()

        # Concatenamos y normalizamos los campos de búsqueda
        df['search_text'] = df[['procedure_name', 'synonyms', 'raw_text']].fillna('').agg(' '.join, axis=1)
        df['search_text'] = df['search_text'].apply(normalize_text)

        # Buscamos coincidencias que contengan todas las palabras de la query
        for _, fila in df.iterrows():
            if all(word in fila['search_text'] for word in query_words):
                resultados.append(fila.to_dict())

        if not resultados:
            return json.dumps({
                "mensaje": f"No se encontró ninguna cirugía o tratamiento con el nombre '{name_surgery_or_treatment}'.",
                "nota": "💡 Los precios mostrados son aproximados y pueden variar según el procedimiento y la valoración médica."
            })

        return json.dumps({
            "resultados": resultados,
            "nota": "💡 Los precios listados son valores aproximados del dataset médico y pueden variar según el paciente, la clínica y el contexto del tratamiento."
        })

    except Exception as e:
        logger.error(f"❌ Error en procedures_and_treatments_price_list: {e}")
        return json.dumps({
            "error": f"Ocurrió un error leyendo el CSV desde Azure Blob: {str(e)}",
            "nota": "💡 Los precios del dataset son referenciales y pueden variar."
        })

async def transfer_chat_to_operators(
        department_id: str,
        conversation_id: str,
        operator_id: Optional[str]=None,
        timeout: float = 10.0
    ):
    url = f'https://salesiq.zoho.com/api/v2/{constants.SCREENNAME}/conversations/{conversation_id}/transfer'
    ZOHO_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN")

    Payload = {
        "department_id" : "19000000000017",
        "operator_id" : "19000000026003",
        "note":"The previous deal was closed"
    }

    headers = {
        "Authorization": f"Zoho-oauthtoken {ZOHO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url=url, json=Payload, headers=headers)
    except httpx.RequestError as e:
        logger.error(
            "Zoho connection error",
            extra={
                "url": url,
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=502,
            detail=f"Zoho connection error: {str(e)}"
        )
    
    if resp.status_code not in (200, 204):
        logger.error(
            "Zoho API error",
            extra={
                "url": url,
                "status": resp.status_code,
            }
        )
        raise HTTPException(
            status_code=500,
            detail=f"Zoho API error {resp.status_code}: {resp.text}"
        )

tools = [
    {
        "type": "function",
        "function": {
            "name": "is_customer_service_available",
            "description": "Comprueba si el servicio de atención al cliente está disponible actualmente en España. "
                            "Utilízala cuando el usuario pregunte si puede ser atendido por un asesor, "
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
