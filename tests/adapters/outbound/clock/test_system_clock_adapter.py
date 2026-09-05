from datetime import datetime, timezone

from app.adapters.outbound.clock.system_clock_adapter import SystemClockAdapter


async def test_now_returns_timezone_aware_utc_close_to_real_time():
    adapter = SystemClockAdapter()

    before = datetime.now(timezone.utc)
    result = await adapter.now()
    after = datetime.now(timezone.utc)

    assert result.tzinfo is not None
    assert before <= result <= after
