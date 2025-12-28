import os
import re
import json
import httpx
import holidays
import unicodedata
from typing import Optional
from zoneinfo import ZoneInfo
from app.core import constants
from fastapi import HTTPException, Request
from datetime import datetime, time
from app.services.db import connection
from app.core.logging_config import logger
from app.services.chat.zoho_payload import parse_zoho_payload
from app.services.cloud.azure.azure_blob import AzureBlobService


# Obtener hora actual de España
def get_current_time_spain() -> datetime:
    madrid_tz = ZoneInfo("Europe/Madrid")
    return datetime.now(madrid_tz)

# def is_customer_service_available(input: str = ""):
#     now = get_current_time_spain()
#     dia_semana = now.weekday()  # Lunes=0, Domingo=6
#     es_holidays = holidays.Spain(years=now.year)

#     # Domingo o festivo
#     if dia_semana == 6 or now.date() in es_holidays:
#         return json.dumps({
#             "message": "El servicio de atención al cliente no está disponible hoy (domingo o festivo)."
#         })

#     # Horario laboral
#     message = "El servicio de atención al cliente no está disponible en este momento."

#     if 0 <= dia_semana <= 4:
#         if time(8, 0) <= now.time() <= time(12, 0) or time(14, 0) <= now.time() <= time(18, 0):
#             message = "El servicio de atención al cliente está disponible actualmente."
#     elif dia_semana == 5:
#         if time(8, 0) <= now.time() <= time(12, 0):
#             message = "El servicio de atención al cliente está disponible actualmente."

#     return json.dumps({"message": message})

def is_customer_service_available(input: str = "") -> str:
    # funcion probar donde siempre estan disponibles el personal de atencion al cliente
    return json.dumps({
        "available": True,
        "reason": "forced_available_for_testing",
        "message": "Customer service is available. You may transfer the conversation to a human agent."
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
    conversation_id: str,
    department_id: str,
    operator_id: Optional[str] = None,
) -> dict:
    """

    Tool terminal: transfers the conversation to a human advisor.

    """
    url = (
        f"https://salesiq.zoho.com/api/v2/{constants.SCREENNAME}/conversations/{conversation_id}/transfer"
    )

    payload = {
        "department_id": department_id,
        "note": constants.CLOSED_CONVERSATION_NOTE
    }

    if operator_id:
        payload["operator_id"] = operator_id

    headers = {
        "Authorization": f"Zoho-oauthtoken {os.getenv('ZOHO_ACCESS_TOKEN')}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"📤 Zoho transfer URL: {url}")
            logger.info(f"📤 Zoho transfer payload: {payload}")
            resp = await client.post(url, json=payload, headers=headers)
            logger.info(f"📥 Zoho transfer response code: {resp.status_code}")
            logger.info(f"📥 Zoho transfer response body: {resp.text}")

        if resp.status_code not in (200, 204):
            logger.error(
                "Zoho agent transfer failed",
                extra={
                    "conversation_id": conversation_id,
                    "status": resp.status_code,
                    "response": resp.text,
                }
            )
            return {
                "status": "error",
                "reason": "zoho_api_error",
                "conversation_closed": False,
            }

        logger.info(
            "Conversation transferred",
            extra={
                "conversation_id": conversation_id,
                "department_id": department_id,
                "operator_id": operator_id,
            }
        )
        return {
            "status": "success",
            "conversation_closed": True,
        }
    except Exception as e:
        logger.exception(
            "zoho_agent_transfer_exception",
            extra={
                "conversation_id": conversation_id,
                "error": str(e),
            },
        )

        return {
            "status": "error",
            "reason": "exception",
            "conversation_closed": False,
        }

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
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_chat_to_operators",
            "description":  (
                "Transfers the active conversation to a human agent in Zoho SalesIQ. "
                "This is a terminal action: once executed successfully, the assistant must stop responding "
                "and the conversation is handled by a human operator."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": (
                            "Zoho SalesIQ conversation identifier."
                            "This value uniquely identifies the active chat session"
                            "and is used by the backend to route or transfer the conversation."
                        ),
                    },
                    "department_id": {
                        "type": "string",
                        "description": (
                            "Zoho SalesIQ department identifier. "
                            "This value specifies the department to which the active chat will be transferred."
                        ),
                    },                    
                    "operator_id": {
                        "type": "string",
                        "description": (
                            "Optional Zoho SalesIQ operator ID. "
                            "If omitted, Zoho will assign any available operator in the specified department."
                        ),
                    },
                },
                "required": ["department_id"],
            },
        }
    },
]
