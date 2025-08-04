# app/services/storage/upload_blob.py

import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from io import BytesIO

load_dotenv()

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)

def upload_file_to_blob(blob_name: str, content: bytes):
    stream = BytesIO(content)
    container_client.upload_blob(name=blob_name, data=stream, overwrite=True)
