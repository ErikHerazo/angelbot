from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    async def now(self) -> datetime:
        """Returns the current instant, timezone-aware (UTC)."""
        ...
