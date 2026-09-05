from app.composition_root import build_check_business_availability


async def test_builds_and_runs_against_real_agb_config_and_real_clock():
    use_case = build_check_business_availability()

    result = await use_case.execute("agb")

    assert isinstance(result, bool)
