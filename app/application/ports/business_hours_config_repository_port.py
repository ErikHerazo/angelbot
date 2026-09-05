from typing import Protocol

from app.domain.value_objects.business_hours import BusinessHoursSchedule


class BusinessHoursConfigRepositoryPort(Protocol):
    async def get_schedule(self, tenant_id: str) -> BusinessHoursSchedule: ...
