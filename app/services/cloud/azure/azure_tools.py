import holidays
from zoneinfo import ZoneInfo
from datetime import datetime, time


# Obtener hora actual de España
def get_current_time_spain() -> datetime:
    madrid_tz = ZoneInfo("Europe/Madrid")
    return datetime.now(madrid_tz)

import holidays
from zoneinfo import ZoneInfo
from datetime import datetime, time
import json

# Obtener hora actual de España
def get_current_time_spain() -> datetime:
    madrid_tz = ZoneInfo("Europe/Madrid")
    return datetime.now(madrid_tz)

def is_customer_service_available(input: str = "") -> str:
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


# def is_customer_service_available(input: str = "") -> str:
#     """
#     Indica si el personal de servicio al cliente está disponible actualmente en la clinica.
    
#     Retorna un string JSON con:
#       - available: True/False
#       - message: texto explicativo que el modelo puede usar.
#     """
#     # now = get_current_time_spain()
#     # dia_semana = now.weekday()  # Lunes=0, Domingo=6

#     # # Lista de festivos en España
#     # es_holidays = holidays.Spain(years=now.year)

#     # available = False
#     # message = "El servicio de atención al cliente no está disponible en este momento."

#     # # Horario de lunes a viernes
#     # if 0 <= dia_semana <= 4:
#     #     if time(8,0) <= now.time() <= time(12,0) or time(14,0) <= now.time() <= time(18,0):
#     #         available = True
#     #         message = "El servicio de atención al cliente está disponible actualmente."

#     # # Horario sábado
#     # elif dia_semana == 5:
#     #     if time(8,0) <= now.time() <= time(12,0):
#     #         available = True
#     #         message = "El servicio de atención al cliente está disponible actualmente."

#     # # Domingo o festivo
#     # if dia_semana == 6 or now.date() in es_holidays:
#     #     available = False
#     #     message = "El servicio de atención al cliente no está disponible en este momento."

#     # return test available=True
#     return json.dumps({
#         "available": True,
#         "message": "El servicio de atención al cliente está disponible actualmente."
#     })


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
                    "required": [],
                },
            }
        },
    ]
