import re
import unicodedata

# Umbral real de la clínica (MINOR_SAFETY_RULE): las restricciones aplican
# solo a menores de 16 años, no al umbral legal general español de mayoría
# de edad (18). Único lugar donde vive este número -- tanto la guarda de
# menores (minor_patient_guard.py) como el recordatorio de refuerzo para
# el prompt (más abajo) derivan de esta misma constante y de la misma
# extracción de edad, en vez de que cada regla la reimplemente por su lado.
MINOR_AGE_THRESHOLD = 16
LEGAL_ADULT_AGE = 18

_AGE_PATTERN = re.compile(r"\b(\d{1,2})\s*años\b")

# Respuesta corta a "¿qué edad tiene?" sin la palabra "años" ("14",
# "tiene 14", "14!") -- solo cuenta si el turno anterior del bot preguntó
# la edad, para no confundir cualquier número suelto con una edad.
_BARE_AGE_ANSWER_PATTERN = re.compile(r"^\D{0,20}?(\d{1,2})\D{0,10}$")

_PRICE_INTENT_TERMS = ("precio", "cuesta", "cuestan", "costo", "coste", "cuanto vale", "presupuesto", "tarifa")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


def extract_youngest_age(*texts: str) -> int | None:
    """Busca menciones de edad ("X años") en uno o más textos y devuelve la
    más joven encontrada -- si se mencionan varias edades en la
    conversación, la más joven es la que importa para las reglas de
    seguridad de menores.
    """
    ages = [int(m) for text in texts for m in _AGE_PATTERN.findall(text or "")]
    return min(ages) if ages else None


def extract_age_from_user_turn(user_text: str, previous_assistant_text: str | None) -> int | None:
    """Edad dicha por el usuario en un turno concreto: "X años" en su
    mensaje, o un número suelto si el bot justo antes preguntó la edad.
    """
    age = extract_youngest_age(user_text)
    if age is not None:
        return age
    if previous_assistant_text and "edad" in _normalize(previous_assistant_text):
        match = _BARE_AGE_ANSWER_PATTERN.match((user_text or "").strip())
        if match:
            return int(match.group(1))
    return None


def extract_youngest_age_from_history(history: list[dict]) -> int | None:
    """Edad más joven dicha por el *usuario* en turnos anteriores. Ignora
    deliberadamente los mensajes del bot: su propia respuesta ("dado que tu
    hija tiene 14 años...") no es una edad nueva, y leerla dejaba la guarda
    de menores disparándose en cada mensaje posterior de la sesión --
    confirmado en prod el 2026-09-24 (un "es para mí" o una consulta de
    angustia recibían la plantilla de menores).
    """
    ages = []
    previous_assistant_text = None
    for message in history or []:
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if message.get("role") == "assistant":
            previous_assistant_text = content
        elif message.get("role") == "user":
            age = extract_age_from_user_turn(content, previous_assistant_text)
            if age is not None:
                ages.append(age)
    return min(ages) if ages else None


def has_price_intent(text: str) -> bool:
    normalized = _normalize(text)
    return any(term in normalized for term in _PRICE_INTENT_TERMS)


def age_reinforcement_note(patient_age: int | None) -> str:
    """Nota de refuerzo para el prompt según la edad ya conocida en la
    conversación. Devuelve "" si no hay edad o es adulto (nada que aclarar).

    - Menor de 16: la guarda de menores solo corta en el turno en que se da
      la edad o si luego se pide precio; el resto de turnos llega al modelo,
      que necesita saber que la regla sigue aplicando a *ese* paciente sin
      bloquear temas distintos (p. ej. el propio usuario consultando algo
      para sí mismo).
    - 16-17: MINOR_SAFETY_RULE solo restringe a menores de 16, pero el
      modelo confunde a veces "menor de edad" (umbral legal general, 18)
      con el umbral específico de esta clínica -- confirmado en vivo.
    """
    if patient_age is None:
        return ""
    if patient_age < MINOR_AGE_THRESHOLD:
        return (
            f"NOTA DEL SISTEMA: en esta conversación se indicó un paciente de {patient_age} años "
            f"(menor de {MINOR_AGE_THRESHOLD}). Para cualquier consulta sobre ese paciente aplica "
            "la regla de seguridad de menores: no des precios ni confirmes candidatura, deriva a "
            "valoración con un especialista. Si el mensaje actual trata de otro tema o de otra "
            "persona (por ejemplo, el propio usuario consultando algo para sí mismo), respóndelo "
            "con normalidad según el resto de reglas."
        )
    if patient_age < LEGAL_ADULT_AGE:
        return (
            f"NOTA DEL SISTEMA (edad ya confirmada en esta conversación: {patient_age} años): "
            f"{patient_age} años NO es menor de {MINOR_AGE_THRESHOLD} años según el umbral real "
            "de la regla de seguridad de menores de esta clínica. Puedes dar precio, información "
            "del procedimiento y confirmar candidatura con normalidad para este paciente (salvo "
            "que otra regla de desambiguación indique lo contrario). No niegues esta información "
            "solo por tratarse de un menor de edad en el sentido legal general (menor de 18)."
        )
    return ""
