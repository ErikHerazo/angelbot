import logging
from azure.search.documents.indexes import SearchIndexerClient
from azure.core.credentials import AzureKeyCredential
from app.core.config import Settings

logger = logging.getLogger(__name__)


class AzureSearchService:

    def __init__(self):

        self.indexer_name = Settings.AZURE_SEARCH_INDEXER_NAME

        self.client = SearchIndexerClient(
            endpoint=Settings.AZURE_SEARCH_ENDPOINT,
            credential=AzureKeyCredential(Settings.AZURE_SEARCH_ADMIN_KEY)
        )


    def get_indexer_status(self):

        status = self.client.get_indexer_status(self.indexer_name)

        return {
            "status": status.status,
            "last_result": str(status.last_result.status) if status.last_result else None
        }

    def run_indexer(self):

        try:

            status = self.client.get_indexer_status(self.indexer_name)

            if status.status.lower() == "running":
                logger.info("Indexer already running")
                return {"status": "already_running"}

            self.client.run_indexer(self.indexer_name)

            logger.info(f"Indexer {self.indexer_name} started")

            return {"status": "started"}

        except Exception as e:

            logger.exception("Error running indexer")

            return {
                "status": "error",
                "message": str(e)
            }