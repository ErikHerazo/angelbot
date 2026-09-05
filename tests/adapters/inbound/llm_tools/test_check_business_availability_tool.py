import json

from app.adapters.inbound.llm_tools.check_business_availability_tool import (
    CheckBusinessAvailabilityTool,
)


class FakeUseCase:
    def __init__(self, result):
        self._result = result
        self.calls = []

    async def execute(self, tenant_id):
        self.calls.append(tenant_id)
        return self._result


async def test_returns_available_true_as_json():
    use_case = FakeUseCase(result=True)
    tool = CheckBusinessAvailabilityTool(use_case=use_case, tenant_id="agb")

    result = await tool(input="")

    parsed = json.loads(result)
    assert parsed["available"] is True
    assert use_case.calls == ["agb"]


async def test_returns_available_false_as_json():
    use_case = FakeUseCase(result=False)
    tool = CheckBusinessAvailabilityTool(use_case=use_case, tenant_id="agb")

    result = await tool()

    parsed = json.loads(result)
    assert parsed["available"] is False
