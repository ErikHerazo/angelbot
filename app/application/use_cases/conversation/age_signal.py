import re

# Umbral real de la clínica (MINOR_SAFETY_RULE): las restricciones aplican
# solo a menores de 16 años, no al umbral legal general español de mayoría
# de edad (18). Único lugar donde vive este número -- tanto la guarda de
# menores (minor_patient_guard.py) como el recordatorio de refuerzo para
# 16-17 años (más abajo) derivan de esta misma constante y de la misma
# extracción de edad, en vez de que cada regla la reimplemente por su lado.
MINOR_AGE_THRESHOLD = 16
LEGAL_ADULT_AGE = 18

_AGE_PATTERN = re.compile(r"\b(\d{1,2})\s*años\b")


def extract_youngest_age(*texts: str) -> int | None:
    """Busca menciones de edad ("X años") en uno o más textos (mensaje
    actual + historial concatenado) y devuelve la más joven encontrada --
    si se mencionan varias edades en la conversación, la más joven es la
    que importa para las reglas de seguridad de menores.
    """
    ages = [int(m) for text in texts for m in _AGE_PATTERN.findall(text or "")]
    return min(ages) if ages else None


def age_reinforcement_note(patient_age: int | None) -> str:
    """Nota de refuerzo para el prompt cuando la edad ya conocida está en
    la banda ambigua 16-17: MINOR_SAFETY_RULE solo restringe a menores de
    16, pero el modelo confunde a veces "menor de edad" (umbral legal
    general, 18) con el umbral específico de esta clínica -- confirmado en
    vivo (ver memoria de sesión). Devuelve "" fuera de esa banda (nada que
    aclarar: o ya lo bloquea la guarda de menores, o es mayor de edad sin
    ambigüedad).
    """
    if patient_age is not None and MINOR_AGE_THRESHOLD <= patient_age < LEGAL_ADULT_AGE:
        return (
            f"NOTA DEL SISTEMA (edad ya confirmada en esta conversación: {patient_age} años): "
            f"{patient_age} años NO es menor de {MINOR_AGE_THRESHOLD} años según el umbral real "
            "de la regla de seguridad de menores de esta clínica. Puedes dar precio, información "
            "del procedimiento y confirmar candidatura con normalidad para este paciente (salvo "
            "que otra regla de desambiguación indique lo contrario). No niegues esta información "
            "solo por tratarse de un menor de edad en el sentido legal general (menor de 18)."
        )
    return ""
