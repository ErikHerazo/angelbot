import os
from dotenv import load_dotenv

# Carga las variables del .env
load_dotenv(dotenv_path="/app/.env")
APP_ENV = os.getenv("APP_ENV", "local")

class Settings:
    # Blob
    AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")  # <- apunta a la variable correcta
    PRICE_LIST_CONTAINER = os.getenv("PRICE_LIST_CONTAINER")
    PRICE_LIST_BLOB = os.getenv("PRICE_LIST_BLOB")

    # Azure AD
    AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_AI_SEARCH_API_KEY")
    AZURE_SEARCH_INDEXER_NAME = os.getenv("AZURE_AI_SEARCH_INDEXER")

    # Redis
    if APP_ENV == "prod":
        REDIS_HOST = os.getenv("REDIS_HOST_PROD")
        REDIS_PORT = os.getenv("REDIS_PORT_PROD")
        REDIS_PASSWORD = os.getenv("REDIS_PASSWORD_PROD")

        CELERY_BROKER_URL = (
            f"rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
            "?ssl_cert_reqs=CERT_NONE"
        )

        CELERY_RESULT_BACKEND = (
            f"rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
            "?ssl_cert_reqs=CERT_NONE"
        )
    else:
        CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL_LOCAL")
        CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND_LOCAL")

settings = Settings()

# 🔐 Validación crítica al arrancar
if not settings.AZURE_CLIENT_ID:
    raise RuntimeError("AZURE_CLIENT_ID not configured")

if not settings.AZURE_TENANT_ID:
    raise RuntimeError("AZURE_TENANT_ID not configured")

if not Settings.AZURE_SEARCH_ENDPOINT:
    raise RuntimeError("AZURE_AI_SEARCH_ENDPOINT not configured")

if not Settings.AZURE_SEARCH_ADMIN_KEY:
    raise RuntimeError("AZURE_AI_SEARCH_API_KEY not configured")

if not Settings.AZURE_SEARCH_INDEXER_NAME:
    raise RuntimeError("AZURE_AI_SEARCH_INDEXER not configured")

if not Settings.CELERY_BROKER_URL:
    raise RuntimeError("CELERY_BROKER_URL not configured")

if not Settings.CELERY_RESULT_BACKEND:
    raise RuntimeError("CELERY_RESULT_BACKEND not configured")
