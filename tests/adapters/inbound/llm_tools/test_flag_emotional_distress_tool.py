import json

from app.adapters.inbound.llm_tools.flag_emotional_distress_tool import FlagEmotionalDistressTool


async def test_always_returns_acknowledged_true():
    tool = FlagEmotionalDistressTool()

    result = await tool("cualquier texto")

    assert json.loads(result) == {"acknowledged": True}


async def test_input_is_optional():
    tool = FlagEmotionalDistressTool()

    result = await tool()

    assert json.loads(result) == {"acknowledged": True}
