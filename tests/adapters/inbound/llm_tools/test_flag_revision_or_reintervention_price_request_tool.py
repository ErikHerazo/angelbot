import json

from app.adapters.inbound.llm_tools.flag_revision_or_reintervention_price_request_tool import (
    FlagRevisionOrReinterventionPriceRequestTool,
)


async def test_always_returns_acknowledged_true():
    tool = FlagRevisionOrReinterventionPriceRequestTool()

    result = await tool("cualquier texto")

    assert json.loads(result) == {"acknowledged": True}


async def test_input_is_optional():
    tool = FlagRevisionOrReinterventionPriceRequestTool()

    result = await tool()

    assert json.loads(result) == {"acknowledged": True}
