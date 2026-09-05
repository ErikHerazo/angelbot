from app.application.ports.price_catalog_search_port import PriceCatalogSearchPort
from app.application.ports.tenant_repository_port import TenantRepositoryPort
from app.core.logging.structured_logger import get_logger
from app.domain.value_objects.procedure_price import ProcedurePriceResult, normalize_search_text

DEFAULT_CURRENCY = "EUR"

log = get_logger(__name__)


class LookupProcedurePrice:
    def __init__(
        self,
        *,
        tenant_repository: TenantRepositoryPort,
        price_catalog_search: PriceCatalogSearchPort,
    ):
        self._tenant_repository = tenant_repository
        self._price_catalog_search = price_catalog_search

    async def execute(
        self,
        tenant_id: str,
        name_surgery_or_treatment: str,
    ) -> list[ProcedurePriceResult]:
        with log.operation(tenant_id=tenant_id, raw_query=name_surgery_or_treatment):
            query = normalize_search_text(name_surgery_or_treatment)
            if not query:
                log.warning("Blank query after normalization, skipping catalog search")
                return []

            tenant = await self._tenant_repository.get_tenant(tenant_id)
            matches = await self._price_catalog_search.search(query)
            log.info("Catalog search finished", normalized_query=query, matches=len(matches))

            currency = tenant.default_currency or DEFAULT_CURRENCY

            return [
                ProcedurePriceResult(
                    procedure_name=match.procedure_name,
                    price_range=match.price_range,
                    currency=currency,
                )
                for match in matches
            ]
