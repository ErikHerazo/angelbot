import os
from dotenv import load_dotenv

# Carga las variables del .env
load_dotenv(dotenv_path="/app/.env")

class Settings:
    AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")  # <- apunta a la variable correcta
    PRICE_LIST_CONTAINER = os.getenv("PRICE_LIST_CONTAINER")
    PRICE_LIST_BLOB = os.getenv("PRICE_LIST_BLOB")

settings = Settings()
