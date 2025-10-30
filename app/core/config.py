import os
from dotenv import load_dotenv

# Cargar variables del .env
load_dotenv()

class Settings:
    AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
    PRICE_LIST_CONTAINER = os.getenv("PRICE_LIST_CONTAINER")
    PRICE_LIST_BLOB = os.getenv("PRICE_LIST_BLOB")

settings = Settings()
