import json
import holidays
from zoneinfo import ZoneInfo
from datetime import datetime, time
from app.services.db import connection


# Obtener hora actual de España
def get_current_time_spain() -> datetime:
    madrid_tz = ZoneInfo("Europe/Madrid")
    return datetime.now(madrid_tz)

def is_customer_service_available(input: str = ""):
    """
    Indica si el personal de servicio al cliente está disponible actualmente en la clinica.
    
    Retorna un string JSON con:
      - available: True/False
      - message: texto explicativo que el modelo puede usar.
    """
    now = get_current_time_spain()
    dia_semana = now.weekday()  # Lunes=0, Domingo=6

    # Lista de festivos en España
    es_holidays = holidays.Spain(years=now.year)

    available = False
    message = "El servicio de atención al cliente no está disponible en este momento."

    # Horario de lunes a viernes
    if 0 <= dia_semana <= 4:
        if time(8,0) <= now.time() <= time(12,0) or time(14,0) <= now.time() <= time(18,0):
            available = True
            message = "El servicio de atención al cliente está disponible actualmente."

    # Horario sábado
    elif dia_semana == 5:
        if time(8,0) <= now.time() <= time(12,0):
            available = True
            message = "El servicio de atención al cliente está disponible actualmente."

    # Domingo o festivo
    if dia_semana == 6 or now.date() in es_holidays:
        available = False
        message = "El servicio de atención al cliente no está disponible en este momento."

    return json.dumps({
        "available": available,
        "message": message
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
    Inserts a new user record into the 'users' table.
    Ensures the table exists before attempting insertion.

    Parameters
    ----------
    name : str
        The user's full name.
    email : str
        The user's email address.

    Retorna un string JSON con:
      - status: True/False
      - message: texto explicativo que el modelo puede usar.
    """
    insert_query = """
        INSERT INTO users (name, email)
        VALUES (?, ?);
    """

    try:
        ensure_users_table()  # Make sure the table exists before insertion

        with connection.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(insert_query, (name, email))
                conn.commit()
        return json.dumps({
            "status": True,
            "message": "The user was saved successfully."
        })
    except Exception as error:
        print(f"❌ Failed to insert user [{email}]: {error}")
        return json.dumps({
            "status": True,
            "message": "The user was not saved."
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
