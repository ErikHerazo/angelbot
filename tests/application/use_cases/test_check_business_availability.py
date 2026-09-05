from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.application.use_cases.check_business_availability import CheckBusinessAvailability
from app.domain.entities.tenant import Tenant
from app.domain.value_objects.business_hours import BusinessHoursSchedule, BusinessHoursWindow


class FakeTenantRepository:
    def __init__(self, tenant):
        self._tenant = tenant

    async def get_tenant(self, tenant_id):
        return self._tenant


class FakeBusinessHoursConfig:
    def __init__(self, schedule):
        self._schedule = schedule

    async def get_schedule(self, tenant_id):
        return self._schedule


class FakeClock:
    def __init__(self, fixed_now):
        self._fixed_now = fixed_now

    async def now(self):
        return self._fixed_now


AGB_TENANT = Tenant(
    tenant_id="agb",
    legal_name="Cosmetic Surgery BCN SLP",
    trade_name="Antiaging Group Barcelona",
    address="Ronda general Mitre 84",
    city="Barcelona",
    country="ES",
    tax_id="B63819130",
    timezone="Europe/Madrid",
)

# lunes con ventana 10:30-14:00
SCHEDULE = BusinessHoursSchedule(
    windows_by_weekday={0: [BusinessHoursWindow(time(10, 30), time(14, 0))]}
)


def make_use_case(fixed_now):
    return CheckBusinessAvailability(
        tenant_repository=FakeTenantRepository(AGB_TENANT),
        business_hours_config=FakeBusinessHoursConfig(SCHEDULE),
        clock=FakeClock(fixed_now),
    )


async def test_returns_true_when_open_and_not_holiday():
    # 2026-01-05 es lunes y no es festivo en España
    fixed_now = datetime(2026, 1, 5, 11, 0, tzinfo=ZoneInfo("Europe/Madrid"))

    assert await make_use_case(fixed_now).execute("agb") is True


async def test_returns_false_on_public_holiday_even_during_window():
    # 2026-10-12 es lunes (dentro de la ventana horaria) pero es Fiesta
    # Nacional en España -- si esto diera True, el chequeo de festivos
    # no se estaría aplicando de verdad.
    fixed_now = datetime(2026, 10, 12, 11, 0, tzinfo=ZoneInfo("Europe/Madrid"))

    assert await make_use_case(fixed_now).execute("agb") is False


async def test_returns_false_outside_window():
    fixed_now = datetime(2026, 1, 5, 20, 0, tzinfo=ZoneInfo("Europe/Madrid"))

    assert await make_use_case(fixed_now).execute("agb") is False
