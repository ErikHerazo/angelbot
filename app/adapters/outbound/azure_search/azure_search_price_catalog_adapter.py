import httpx

from app.domain.value_objects.procedure_price import ProcedureMatch


class AzureSearchPriceCatalogAdapter:
    """Implements PriceCatalogSearchPort against an Azure AI Search index.

    Uses httpx.AsyncClient (the legacy azure_tools.py version used the
    synchronous `requests` library, blocking the event loop on every call --
    fixed here, not just ported forward).
    """

    def __init__(self, *, search_endpoint: str, index_name: str, api_key: str):
        self._url = (
            f"{search_endpoint}/indexes/{index_name}/docs/search"
            "?api-version=2025-11-01-preview"
        )
        self._headers = {"Content-Type": "application/json", "api-key": api_key}

    async def search(self, query: str) -> list[ProcedureMatch]:
        payload = {"search": query, "searchMode": "all", "count": True}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self._url, headers=self._headers, json=payload)

        response.raise_for_status()

        docs = response.json().get("value", [])

        return [
            ProcedureMatch(
                procedure_name=doc.get("procedure_name", ""),
                price_range=doc.get("price_range_eur", ""),
            )
            for doc in docs
        ]
