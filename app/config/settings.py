"""Shared technical settings: not secrets, not tenant-specific business
config -- just fixed technical constraints/values reused across the app.
Deliberately its own module, separate from app/config/tenants/ (per-tenant
business config) and SecretsPort (secrets), per the config/secrets/constants
split agreed early in the hexagonal migration.
"""

import os

import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agent_config.yaml")
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _shared_config = yaml.safe_load(_f)

# LangGraph agent (app/application/use_cases/conversation/) -- shared,
# non-tenant-specific technical config, same "one YAML with named blocks"
# structure as config/tenants/{tenant_id}/config.yaml, not hardcoded Python.
MAX_TOOL_ITERATIONS = _shared_config["retrieval"]["max_tool_iterations"]
# Env var overrides the committed YAML value when set -- needed because
# agent_config.yaml is one shared file checked into git (currently pointing
# at the deployed Azure internal URLs for staging), but local dev needs to
# reach the local docker-compose MCP servers on localhost instead. Every
# deployed environment (staging/prod) leaves these unset and gets the YAML
# value as-is.
MCP_AZURE_SEARCH_URL = os.getenv("MCP_AZURE_SEARCH_URL", _shared_config["mcp_servers"]["azure_search_url"])
MCP_ZOHO_URL = os.getenv("MCP_ZOHO_URL", _shared_config["mcp_servers"]["zoho_url"])

# Bearer tokens for the 2 clinyq-mcp-* servers above -- secrets, so env vars
# (never agent_config.yaml), same as every other secret in this codebase.
# Shared across tenants (this agent is the single known caller of both
# servers today), unlike SecretsPort's tenant-scoped secrets.
MCP_AZURE_SEARCH_AUTH_TOKEN = os.getenv("MCP_AZURE_SEARCH_AUTH_TOKEN")
MCP_ZOHO_AUTH_TOKEN = os.getenv("MCP_ZOHO_AUTH_TOKEN")

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
