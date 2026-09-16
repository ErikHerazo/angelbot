from datetime import time

from app.adapters.outbound.tenant_config.tenant_config_file import read_tenant_config_block
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
    """Implements BusinessHoursConfigRepositoryPort, reading the
    "business_hours" block from config/tenants/{tenant_id}/config.yaml."""

    def __init__(self, config_dir: str):
        self._config_dir = config_dir

    async def get_schedule(self, tenant_id: str) -> BusinessHoursSchedule:
        data = await read_tenant_config_block(self._config_dir, tenant_id, "business_hours")
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
