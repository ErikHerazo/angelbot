import json

from app.adapters.inbound.llm_tools.flag_minor_patient_tool import FlagMinorPatientTool


async def test_always_returns_acknowledged_true():
    tool = FlagMinorPatientTool()

    result = await tool("cualquier texto")

    assert json.loads(result) == {"acknowledged": True}


async def test_input_is_optional():
    tool = FlagMinorPatientTool()

    result = await tool()

    assert json.loads(result) == {"acknowledged": True}
