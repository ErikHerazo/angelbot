"""Shared technical settings: not secrets, not tenant-specific business
config -- just fixed technical constraints/values reused across the app.
Deliberately its own module, separate from app/config/tenants/ (per-tenant
business config) and SecretsPort (secrets), per the config/secrets/constants
split agreed early in the hexagonal migration.
"""

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx", ".png", ".jpg", ".csv", ".xlsx"}
MAX_FILE_SIZE_MB = 10
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

MIN_LANG_DETECTION_LEN = 6

INSTAGRAM_CHARACTER_LIMIT = 900

FALLBACK_MESSAGE = (
    "⚠️ Your request could not be processed at this time. "
    "Please try again."
)

# Nombres legibles para instruir al LLM en qué idioma responder -- no implica
# soporte oficial/restricción, es solo para que la instrucción de idioma en
# el prompt use un nombre en vez de un código ISO crudo.
LANGUAGE_DISPLAY_NAMES = {
    "en": "Inglés",
    "es": "Español",
    "ru": "Ruso",
    "ca": "Catalán",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "pt": "Portugués",
    "ar": "Árabe",
    "nl": "Neerlandés",
    "zh": "Chino",
    "ja": "Japonés",
    "hi": "Hindi",
    "bn": "Bengalí",
    "pa": "Panyabí",
    "id": "Indonesio",
    "ur": "Urdu",
    "ko": "Coreano",
    "vi": "Vietnamita",
    "tr": "Turco",
    "fa": "Persa",
    "sw": "Suajili",
    "th": "Tailandés",
    "pl": "Polaco",
    "uk": "Ucraniano",
    "ro": "Rumano",
    "el": "Griego",
    "he": "Hebreo",
    "fil": "Filipino",
}
