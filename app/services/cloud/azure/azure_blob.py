import re
import io
import pandas as pd
from azure.storage.blob import BlobServiceClient
from app.core.config import settings
from app.core.logging_config import logger


class AzureBlobService:
    def __init__(self):
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                settings.AZURE_BLOB_CONNECTION_STRING
            )
            logger.info("✅ Connection established with Azure Blob Storage.")
        except Exception as e:
            logger.error(f"❌ Error connecting to Azure Blob Storage: {e}")
            raise

    # === READ ===
    def read_csv_from_blob(self, container_name=None, blob_name=None) -> pd.DataFrame:
        container_name = container_name or settings.PRICE_LIST_CONTAINER
        blob_name = blob_name or settings.PRICE_LIST_BLOB

        try:
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            stream = blob_client.download_blob()
            df = pd.read_csv(io.BytesIO(stream.readall()))
            logger.info(f"✅ CSV '{blob_name}' cargado correctamente desde Blob Storage.")
            return df
        except Exception as e:
            logger.error(f"❌ Error leyendo CSV desde Blob Storage: {e}")
            raise

    # === CREATE/UPDATE ===
    def upload_blob(self, container_name, blob_name, file_path):
        try:
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            logger.info(f"✅ Archivo '{blob_name}' subido exitosamente al contenedor '{container_name}'.")
        except Exception as e:
            logger.error(f"❌ Error subiendo blob: {e}")
            raise

    # === DELETE ===
    def delete_blob(self, container_name, blob_name):
        try:
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_client.delete_blob()
            logger.info(f"✅ Blob '{blob_name}' eliminado correctamente del contenedor '{container_name}'.")
        except Exception as e:
            logger.error(f"❌ Error eliminando blob: {e}")
            raise

    # === LIST ===
    def list_blobs(self, container_name):
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            blobs = [b.name for b in container_client.list_blobs()]
            logger.info(f"📦 Blobs encontrados en '{container_name}': {blobs}")
            return blobs
        except Exception as e:
            logger.error(f"❌ Error listando blobs: {e}")
            raise

    # === CREATE/UPDATE (STREAM) ===
    def upload_blob_stream(
        self,
        container_name: str,
        file,
        prefix: str | None = None
    ) -> str:
        try:
            # Basic filename sanitization
            safe_name = file.filename.strip().replace(" ", "_")
            safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "", safe_name)

            # Build blob name using prefix if provided
            if prefix:
                prefix = prefix if prefix.endswith("/") else f"{prefix}/"
                blob_name = f"{prefix}{safe_name}"
            else:
                blob_name = safe_name

            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )

            blob_client.upload_blob(file.file, overwrite=True)

            logger.info(
                f"✅ Archivo '{blob_name}' subido por stream al contenedor '{container_name}'."
            )

            return blob_name

        except Exception as e:
            logger.error(f"❌ Error subiendo blob por stream: {e}")
            raise
    
    # === LIST CONTAINERS ===
    def list_containers(self):
        try:
            containers = [
                container.name
                for container in self.blob_service_client.list_containers()
            ]
            logger.info(f"📦 Contenedores disponibles: {containers}")
            return containers
        except Exception as e:
            logger.error(f"❌ Error listando contenedores: {e}")
            raise

    # === LIST PREFIXES (FOLDERS VIRTUALES) ===
    def list_prefixes(self, container_name: str, parent_prefix: str | None = None):
        try:
            # Validación defensiva
            if not container_name:
                raise ValueError("container_name is required")
            container_client = self.blob_service_client.get_container_client(container_name)
            
            prefixes = []
            
            blob_iterator = container_client.walk_blobs(
                name_starts_with=parent_prefix or "",
                delimiter="/"
            )

            for item in blob_iterator:
                if hasattr(item, "prefix"):
                    prefixes.append(item.prefix)

            logger.info(
                f"📁 Prefixes in '{container_name}' (parent='{parent_prefix}'): {prefixes}"
            )
            return prefixes
        
        except Exception as e:
            logger.error(f"❌ Error listing prefixes: {e}")
            raise
