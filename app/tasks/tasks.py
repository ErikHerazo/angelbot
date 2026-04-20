import logging
from app.services.cloud.azure.azure_search.indexer_service import AzureSearchIndexerService
from app.tasks.celery import app

logger = logging.getLogger(__name__)

@app.task
def add(x, y):
    return x + y

@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries":3})
def run_search_indexer(self):

    try:
        service = AzureSearchIndexerService()

        result = service.run_indexer()

        logger.info(f"Indexer task result: {result}")

        return result

    except Exception as e:
        logger.exception("Indexer task failed")
        raise
