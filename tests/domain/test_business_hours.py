from datetime import date, datetime, time

from app.domain.value_objects.business_hours import (
    BusinessHoursSchedule,
    BusinessHoursWindow,
    is_within_business_hours,
)

MONDAY = date(2026, 1, 5)  # 0 = lunes
SATURDAY = date(2026, 1, 10)

SCHEDULE = BusinessHoursSchedule(
    windows_by_weekday={
        0: [BusinessHoursWindow(time(10, 30), time(14, 0)), BusinessHoursWindow(time(15, 30), time(19, 0))],
        4: [BusinessHoursWindow(time(10, 30), time(14, 0))],
    }
)


def test_open_during_morning_window():
    now = datetime.combine(MONDAY, time(11, 0))
    assert is_within_business_hours(SCHEDULE, holidays=set(), now=now) is True


def test_closed_between_morning_and_afternoon_windows():
    now = datetime.combine(MONDAY, time(14, 30))
    assert is_within_business_hours(SCHEDULE, holidays=set(), now=now) is False


def test_open_during_afternoon_window():
    now = datetime.combine(MONDAY, time(16, 0))
    assert is_within_business_hours(SCHEDULE, holidays=set(), now=now) is True


def test_closed_on_day_with_no_windows_configured():
    now = datetime.combine(SATURDAY, time(11, 0))
    assert is_within_business_hours(SCHEDULE, holidays=set(), now=now) is False


def test_closed_on_holiday_even_during_normal_window():
    now = datetime.combine(MONDAY, time(11, 0))
    assert is_within_business_hours(SCHEDULE, holidays={MONDAY}, now=now) is False
