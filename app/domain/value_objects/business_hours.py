from dataclasses import dataclass, field
from datetime import date, datetime, time


@dataclass
class BusinessHoursWindow:
    start: time
    end: time

    def contains(self, moment: time) -> bool:
        return self.start <= moment <= self.end


@dataclass
class BusinessHoursSchedule:
    # weekday: 0=lunes ... 6=domingo (datetime.weekday()). Un día sin
    # entrada, o con lista vacía, se interpreta como cerrado todo el día.
    windows_by_weekday: dict[int, list[BusinessHoursWindow]] = field(default_factory=dict)


def is_within_business_hours(
    schedule: BusinessHoursSchedule,
    holidays: set[date],
    now: datetime,
) -> bool:
    """Pure rule: no I/O, no `datetime.now()`, no país hardcodeado -- todo
    lo que necesita se lo pasan (schedule, holidays, now ya localizado en
    la timezone del tenant)."""
    if now.date() in holidays:
        return False

    windows = schedule.windows_by_weekday.get(now.weekday(), [])
    current_time = now.time()

    return any(window.contains(current_time) for window in windows)
