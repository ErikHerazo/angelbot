import json

from app.adapters.inbound.llm_tools.lookup_procedure_price_tool import LookupProcedurePriceTool
from app.domain.value_objects.procedure_price import ProcedurePriceResult


class FakeUseCase:
    def __init__(self, results):
        self._results = results
        self.calls = []

    async def execute(self, tenant_id, name_surgery_or_treatment):
        self.calls.append((tenant_id, name_surgery_or_treatment))
        return self._results


async def test_blank_input_returns_no_query_message_without_calling_use_case():
    use_case = FakeUseCase(results=[])
    tool = LookupProcedurePriceTool(use_case=use_case, tenant_id="agb")

    result = await tool("   ")

    parsed = json.loads(result)
    assert parsed["found"] is False
    assert use_case.calls == []


async def test_no_matches_returns_not_found_message():
    use_case = FakeUseCase(results=[])
    tool = LookupProcedurePriceTool(use_case=use_case, tenant_id="agb")

    result = await tool("tratamiento inexistente")

    parsed = json.loads(result)
    assert parsed["found"] is False
    assert parsed["results"] == []
    assert use_case.calls == [("agb", "tratamiento inexistente")]


async def test_matches_returned_as_found_with_results():
    use_case = FakeUseCase(
        results=[ProcedurePriceResult(procedure_name="Rinoplastia", price_range="2000-3000", currency="EUR")]
    )
    tool = LookupProcedurePriceTool(use_case=use_case, tenant_id="agb")

    result = await tool("rinoplastia")

    parsed = json.loads(result)
    assert parsed["found"] is True
    assert parsed["results"] == [
        {"procedure_name": "Rinoplastia", "price_range": "2000-3000", "type_of_currency": "EUR"}
    ]
