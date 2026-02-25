import os
from dotenv import load_dotenv

# Carga las variables del .env
load_dotenv(dotenv_path="/app/.env")

class Settings:
    AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")  # <- apunta a la variable correcta
    PRICE_LIST_CONTAINER = os.getenv("PRICE_LIST_CONTAINER")
    PRICE_LIST_BLOB = os.getenv("PRICE_LIST_BLOB")

    # Azure AD
    AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")

settings = Settings()

# 🔐 Validación crítica al arrancar
if not settings.AZURE_CLIENT_ID:
    raise RuntimeError("AZURE_CLIENT_ID not configured")

if not settings.AZURE_TENANT_ID:
    raise RuntimeError("AZURE_TENANT_ID not configured")
