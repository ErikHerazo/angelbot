import httpx

from app.domain.value_objects.procedure_price import ProcedureMatch


class AzureSearchPriceCatalogAdapter:
    """Implements PriceCatalogSearchPort against an Azure AI Search index.

    Uses httpx.AsyncClient (the legacy azure_tools.py version used the
    synchronous `requests` library, blocking the event loop on every call --
    fixed here, not just ported forward).

    Deliberately does NOT set `searchMode="all"` (Erik's call, 2026-09-09) --
    that value was added to the legacy `azure_tools.py` on 2026-08-27
    specifically to fix a GPT-4o relevance bug (searchMode's Azure default,
    "any", let a single common word like "de" match ~42 unrelated catalog
    entries). This hexagonal adapter is shared by both engines in the
    GPT-4o vs Claude comparison, and inherited that same "all" value when
    it was built -- but "all" has its own failure mode (found the same day
    testing the real multi-procedure case): a legitimate query term not
    present verbatim in the catalog entry (e.g. "parpado" when the entry is
    just "BLEFAROPLASTIA INFERIOR") returns zero results instead of a
    partial match. Erik's bet: Claude reasons better over noisier "any"
    results than GPT-4o did (matches the disambiguation-quality gap already
    seen in the model comparison), so the tradeoff favors reverting to the
    Azure default here -- see ClaudeFoundryConversationEngineAdapter's
    `max_tokens` bump in the same commit, needed because "any" can return
    much more raw data per query for the model to reason over.
    """

    def __init__(self, *, search_endpoint: str, index_name: str, api_key: str):
        self._url = (
            f"{search_endpoint}/indexes/{index_name}/docs/search"
            "?api-version=2025-11-01-preview"
        )
        self._headers = {"Content-Type": "application/json", "api-key": api_key}

    async def search(self, query: str) -> list[ProcedureMatch]:
        payload = {"search": query, "count": True}

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
