import holidays
from zoneinfo import ZoneInfo
from datetime import datetime, time
from langchain_core.tools import tool


# Obtener hora actual de España
def get_current_time_spain() -> datetime:
    madrid_tz = ZoneInfo("Europe/Madrid")
    return datetime.now(madrid_tz)

@tool
async def is_customer_service_available(input: str = "") -> bool:
    """
    Indica si el personal de servicio al cliente está disponible actualmente en España.
    
    Retorna True si estamos dentro del horario de atención, False si no.
    Horarios de atención:
      - Lunes a jueves: 10:30-13:30 y 15:30-19:00
      - viernes: 10:30-13:30
      - Sabados, Domingos y festivos: no disponible
    """
    now = get_current_time_spain()
    dia_semana = now.weekday()  # Lunes=0, Domingo=6

    # Lista de festivos en España
    es_holidays = holidays.Spain(years=now.year)

    # Si es domingo o festivo
    if dia_semana == 6 or now.date() in es_holidays:
        return False

    # Horario de lunes a viernes
    if 0 <= dia_semana <= 3:
        if time(10,30) <= now.time() <= time(13,30) or time(15,30) <= now.time() <= time(19,0):
            return True

    # Horario sábado
    if dia_semana == 4:
        if time(10,30) <= now.time() <= time(14,0):
            return True

    return False


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