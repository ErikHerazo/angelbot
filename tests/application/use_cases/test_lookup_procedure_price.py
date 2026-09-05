from app.application.use_cases.lookup_procedure_price import LookupProcedurePrice
from app.domain.entities.tenant import Tenant
from app.domain.value_objects.procedure_price import ProcedureMatch


class FakeTenantRepository:
    def __init__(self, tenant):
        self._tenant = tenant

    async def get_tenant(self, tenant_id):
        return self._tenant


class FakePriceCatalogSearch:
    def __init__(self, matches):
        self._matches = matches
        self.queries = []

    async def search(self, query):
        self.queries.append(query)
        return self._matches


AGB_TENANT = Tenant(
    tenant_id="agb",
    legal_name="Cosmetic Surgery BCN SLP",
    trade_name="Antiaging Group Barcelona",
    address="Ronda general Mitre 84",
    city="Barcelona",
    country="ES",
    tax_id="B63819130",
    timezone="Europe/Madrid",
    default_currency="EUR",
)

TENANT_WITHOUT_CURRENCY = Tenant(
    tenant_id="clienteb",
    legal_name="Cliente B SA",
    trade_name="Cliente B",
    address="Calle Falsa 123",
    city="Bogotá",
    country="CO",
    tax_id="900123456-7",
    timezone="America/Bogota",
)


async def test_returns_empty_list_for_blank_query():
    search = FakePriceCatalogSearch(matches=[])
    use_case = LookupProcedurePrice(
        tenant_repository=FakeTenantRepository(AGB_TENANT),
        price_catalog_search=search,
    )

    results = await use_case.execute("agb", "   ")

    assert results == []
    assert search.queries == []  # ni siquiera se llama al catálogo


async def test_normalizes_query_and_labels_results_with_tenant_currency():
    search = FakePriceCatalogSearch(
        matches=[ProcedureMatch(procedure_name="Liposuccion de abdomen", price_range="3000-4000")]
    )
    use_case = LookupProcedurePrice(
        tenant_repository=FakeTenantRepository(AGB_TENANT),
        price_catalog_search=search,
    )

    results = await use_case.execute("agb", "¿Liposucción de Abdomen?")

    assert search.queries == ["liposuccion de abdomen"]
    assert len(results) == 1
    assert results[0].procedure_name == "Liposuccion de abdomen"
    assert results[0].price_range == "3000-4000"
    assert results[0].currency == "EUR"


async def test_falls_back_to_eur_when_tenant_has_no_default_currency():
    search = FakePriceCatalogSearch(
        matches=[ProcedureMatch(procedure_name="Rinoplastia", price_range="2000-3000")]
    )
    use_case = LookupProcedurePrice(
        tenant_repository=FakeTenantRepository(TENANT_WITHOUT_CURRENCY),
        price_catalog_search=search,
    )

    results = await use_case.execute("clienteb", "rinoplastia")

    assert results[0].currency == "EUR"
