from datetime import datetime, timezone


class SystemClockAdapter:
    """Implements ClockPort using the real system clock."""

    async def now(self) -> datetime:
        return datetime.now(timezone.utc)
