import logging
from app.services.cloud.azure.azure_search_service import AzureSearchService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def run_search_indexer():

    try:
        service = AzureSearchService()

        result = service.run_indexer()

        logger.info(f"Indexer task result: {result}")

        return result

    except Exception as e:
        logger.exception("Indexer task failed")
        raise
