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
      - Lunes a viernes: 08:00-12:00 y 14:00-18:00
      - Sábado: 08:00-12:00
      - Domingos y festivos: no disponible
    """
    now = get_current_time_spain()
    dia_semana = now.weekday()  # Lunes=0, Domingo=6

    # Lista de festivos en España
    es_holidays = holidays.Spain(years=now.year)

    # Si es domingo o festivo
    if dia_semana == 6 or now.date() in es_holidays:
        return False

    # Horario de lunes a viernes
    if 0 <= dia_semana <= 4:
        if time(8,0) <= now.time() <= time(12,0) or time(14,0) <= now.time() <= time(18,0):
            return True

    # Horario sábado
    if dia_semana == 5:
        if time(8,0) <= now.time() <= time(12,0):
            return True

    return False
