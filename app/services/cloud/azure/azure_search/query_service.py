import os
import requests
import logging
from app.core.config import Settings


logger = logging.getLogger(__name__)

class AzureSearchQueryService:

    def __init__(self):
        self.endpoint = Settings.AZURE_SEARCH_ENDPOINT
        self.index_name = Settings.AZURE_SEARCH_INDEX
        self.api_key = Settings.AZURE_SEARCH_API_KEY

    async def search_unstructured(self, query: str, top_k: int = 5):
        url = f"{self.endpoint}/indexes/{self.index_name}/docs/search?api-version=2025-11-01-preview"

        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }

        payload = {
            "search": query,
            "top": top_k,
            "queryType": "semantic",
            "semanticConfiguration": Settings.SEMANTIC_CONFIGURATION,
            "captions": "extractive",

            # 🔥 hybrid search
            "vectorQueries": [
                {
                    "kind": "text",
                    "text": query,
                    "fields": "text_vector",
                    "k": top_k
                }
            ]
        }

        try:
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise Exception(f"Search error: {response.status_code} - {response.text}")

            results = response.json()
            docs = results.get("value", [])

            chunks = []

            for doc in docs:
                captions = doc.get("@search.captions", [])

                if captions:
                    for c in captions:
                        if c.get("text"):
                            chunks.append(c["text"])
                else:
                    if doc.get("chunk"):
                        chunks.append(doc["chunk"])

            return chunks

        except Exception as e:
            logger.error(f"❌ Error en search_unstructured: {e}")
            return []
        