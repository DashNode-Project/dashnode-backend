"""Domain rules and validation for Availability and Meetings."""

from datetime import date, timedelta

from app.modules.availability.domain import messages
from app.modules.availability.domain.entities import TimeSlot

DAYS_OF_WEEK = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

DAY_LABELS = {
    "monday": "Lunes",
    "tuesday": "Martes",
    "wednesday": "Miércoles",
    "thursday": "Jueves",
    "friday": "Viernes",
    "saturday": "Sábado",
    "sunday": "Domingo",
}


def time_to_minutes(time_str: str) -> int:
    """Converts 'HH:MM' string to minutes from start of day."""
    parts = time_str.split(":")
    if len(parts) != 2:
        msg = f"Invalid time format: {time_str}"
        raise ValueError(msg)
    h, m = int(parts[0]), int(parts[1])
    return h * 60 + m


def minutes_to_time(minutes: int) -> str:
    """Converts minutes to 'HH:MM' string."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def normalize_and_merge_slots(slots: list[TimeSlot]) -> list[TimeSlot]:
    """Merges contiguous or overlapping time slots into sorted non-overlapping ranges."""
    if not slots:
        return []

    # Convert to minute intervals and sort
    intervals: list[tuple[int, int]] = []
    for s in slots:
        start_m = time_to_minutes(s.start)
        end_m = time_to_minutes(s.end)
        if start_m < end_m:
            intervals.append((start_m, end_m))

    if not intervals:
        return []

    intervals.sort(key=lambda x: (x[0], x[1]))

    merged: list[tuple[int, int]] = []
    current_start, current_end = intervals[0]

    for next_start, next_end in intervals[1:]:
        if next_start <= current_end:
            current_end = max(current_end, next_end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = next_start, next_end
    merged.append((current_start, current_end))

    return [TimeSlot(start=minutes_to_time(s), end=minutes_to_time(e)) for s, e in merged]


def are_slots_equal(slots_a: dict[str, list[TimeSlot]], slots_b: dict[str, list[TimeSlot]]) -> bool:
    """Checks if two weekly slot mappings are identical after normalization."""
    for day in DAYS_OF_WEEK:
        norm_a = normalize_and_merge_slots(slots_a.get(day, []))
        norm_b = normalize_and_merge_slots(slots_b.get(day, []))
        if len(norm_a) != len(norm_b):
            return False
        for s1, s2 in zip(norm_a, norm_b, strict=True):
            if s1.start != s2.start or s1.end != s2.end:
                return False
    return True


def validate_search_criteria(
    *,
    interval_start: str,
    interval_end: str,
    days: list[str],
    participant_ids: list[str],
    duration_hours: int,
) -> dict[str, str]:
    """Validates criteria for meeting search according to HU_DN_03_35 criteria."""
    errors: dict[str, str] = {}

    try:
        start_m = time_to_minutes(interval_start)
        end_m = time_to_minutes(interval_end)
        if end_m <= start_m:
            errors["interval"] = messages.INVALID_TIME_INTERVAL
    except (ValueError, TypeError):
        errors["interval"] = messages.INVALID_TIME_INTERVAL
        start_m, end_m = 0, 0

    if not days or not any(d in DAYS_OF_WEEK for d in days):
        errors["days"] = messages.SELECT_AT_LEAST_ONE_DAY

    if not participant_ids:
        errors["participants"] = messages.SELECT_AT_LEAST_ONE_PARTICIPANT

    if duration_hours < 1:
        errors["duration"] = messages.DURATION_WHOLE_HOURS
    elif "interval" not in errors:
        duration_minutes = duration_hours * 60
        if duration_minutes > (end_m - start_m):
            errors["duration"] = messages.DURATION_EXCEEDS_INTERVAL

    return errors


def get_dates_for_week(week_start_date_str: str) -> dict[str, str]:
    """Returns mapping from day name to ISO date (YYYY-MM-DD) for a week starting on Monday."""
    start_date = date.fromisoformat(week_start_date_str)
    # Ensure it's Monday
    monday = start_date - timedelta(days=start_date.weekday())
    result: dict[str, str] = {}
    for i, day_name in enumerate(DAYS_OF_WEEK):
        result[day_name] = (monday + timedelta(days=i)).isoformat()
    return result
