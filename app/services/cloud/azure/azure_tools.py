import json
import pyodbc
import holidays
from zoneinfo import ZoneInfo
from datetime import datetime, time
from app.services.db import connection
from app.core.logging_config import logger


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
                        "message": f"El correo '{email}' ya está registrado. Intente con otro o contacte soporte."
                    })

                # 🆕 Insertar nuevo usuario
                cursor.execute(insert_query, (name, email))
                conn.commit()

        logger.info(f"✅ Usuario registrado correctamente: {name} <{email}>")

        return json.dumps({
            "message": f"Usuario '{name}' con correo '{email}' registrado correctamente."
        })

    except Exception as error:
        logger.error(f"❌ Error al registrar usuario [{email}]: {error}")
        return json.dumps({
            "message": f"No se pudo registrar al usuario '{name}' con correo '{email}'. Error: {error}"
        })

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
]
