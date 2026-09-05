from zoneinfo import ZoneInfo

import holidays as holidays_lib

from app.application.ports.business_hours_config_repository_port import (
    BusinessHoursConfigRepositoryPort,
)
from app.application.ports.clock_port import ClockPort
from app.application.ports.tenant_repository_port import TenantRepositoryPort
from app.domain.value_objects.business_hours import is_within_business_hours


class CheckBusinessAvailability:
    def __init__(
        self,
        *,
        tenant_repository: TenantRepositoryPort,
        business_hours_config: BusinessHoursConfigRepositoryPort,
        clock: ClockPort,
    ):
        self._tenant_repository = tenant_repository
        self._business_hours_config = business_hours_config
        self._clock = clock

    async def execute(self, tenant_id: str) -> bool:
        tenant = await self._tenant_repository.get_tenant(tenant_id)
        schedule = await self._business_hours_config.get_schedule(tenant_id)
        now_utc = await self._clock.now()

        local_now = now_utc.astimezone(ZoneInfo(tenant.timezone))
        country_holidays = holidays_lib.country_holidays(tenant.country, years=local_now.year)

        return is_within_business_hours(
            schedule=schedule,
            holidays=set(country_holidays.keys()),
            now=local_now,
        )
