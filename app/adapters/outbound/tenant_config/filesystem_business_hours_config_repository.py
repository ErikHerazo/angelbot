import asyncio
import os
from datetime import time

import yaml

from app.domain.value_objects.business_hours import BusinessHoursSchedule, BusinessHoursWindow

_WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class FilesystemBusinessHoursConfigRepository:
    """Implements BusinessHoursConfigRepositoryPort, reading business_hours.yaml
    from config/tenants/{tenant_id}/."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_schedule(self, tenant_id: str) -> BusinessHoursSchedule:
        return await asyncio.to_thread(self._read_schedule, tenant_id)

    def _read_schedule(self, tenant_id: str) -> BusinessHoursSchedule:
        path = os.path.join(self._config_dir, tenant_id, "business_hours.yaml")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        raw_schedule = data.get("schedule", {})
        windows_by_weekday = {}

        for weekday_index, weekday_name in enumerate(_WEEKDAY_NAMES):
            raw_windows = raw_schedule.get(weekday_name, [])
            windows_by_weekday[weekday_index] = [
                BusinessHoursWindow(
                    start=time.fromisoformat(start),
                    end=time.fromisoformat(end),
                )
                for start, end in raw_windows
            ]

        return BusinessHoursSchedule(windows_by_weekday=windows_by_weekday)
