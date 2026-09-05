from datetime import time

from app.adapters.outbound.tenant_config.filesystem_business_hours_config_repository import (
    FilesystemBusinessHoursConfigRepository,
)


async def test_reads_agb_business_hours_from_real_config():
    repository = FilesystemBusinessHoursConfigRepository(config_dir="app/config/tenants")

    schedule = await repository.get_schedule("agb")

    monday_windows = schedule.windows_by_weekday[0]
    assert len(monday_windows) == 2
    assert monday_windows[0].start == time(10, 30)
    assert monday_windows[0].end == time(14, 0)
    assert monday_windows[1].start == time(15, 30)

    friday_windows = schedule.windows_by_weekday[4]
    assert len(friday_windows) == 1

    assert schedule.windows_by_weekday[5] == []  # sábado
    assert schedule.windows_by_weekday[6] == []  # domingo
