"""Unit tests for availability domain rules and algorithms."""

import pytest

from app.modules.availability.domain import messages
from app.modules.availability.domain.entities import TimeSlot
from app.modules.availability.domain.rules import (
    are_slots_equal,
    get_dates_for_week,
    minutes_to_time,
    normalize_and_merge_slots,
    time_to_minutes,
    validate_search_criteria,
)


def test_time_conversions() -> None:
    assert time_to_minutes("00:00") == 0
    assert time_to_minutes("09:30") == 570
    assert time_to_minutes("23:59") == 1439
    assert minutes_to_time(570) == "09:30"
    assert minutes_to_time(0) == "00:00"

    with pytest.raises(ValueError, match="Invalid time format"):
        time_to_minutes("invalid")


def test_normalize_and_merge_slots_empty() -> None:
    assert normalize_and_merge_slots([]) == []


def test_normalize_and_merge_contiguous_blocks() -> None:
    # 09:00-10:00 and 10:00-12:00 -> 09:00-12:00
    slots = [
        TimeSlot(start="09:00", end="10:00"),
        TimeSlot(start="10:00", end="12:00"),
    ]
    merged = normalize_and_merge_slots(slots)
    assert len(merged) == 1
    assert merged[0].start == "09:00"
    assert merged[0].end == "12:00"


def test_normalize_and_merge_overlapping_blocks() -> None:
    # 09:00-11:00 and 10:00-12:00 -> 09:00-12:00
    slots = [
        TimeSlot(start="10:00", end="12:00"),
        TimeSlot(start="09:00", end="11:00"),
    ]
    merged = normalize_and_merge_slots(slots)
    assert len(merged) == 1
    assert merged[0].start == "09:00"
    assert merged[0].end == "12:00"


def test_normalize_disjoint_blocks() -> None:
    slots = [
        TimeSlot(start="14:00", end="16:00"),
        TimeSlot(start="09:00", end="11:00"),
    ]
    merged = normalize_and_merge_slots(slots)
    assert len(merged) == 2
    assert merged[0].start == "09:00"
    assert merged[0].end == "11:00"
    assert merged[1].start == "14:00"
    assert merged[1].end == "16:00"


def test_are_slots_equal() -> None:
    slots1 = {
        "monday": [TimeSlot(start="09:00", end="10:00"), TimeSlot(start="10:00", end="11:00")]
    }
    slots2 = {"monday": [TimeSlot(start="09:00", end="11:00")]}
    assert are_slots_equal(slots1, slots2) is True

    slots3 = {"monday": [TimeSlot(start="09:00", end="12:00")]}
    assert are_slots_equal(slots1, slots3) is False


def test_validate_search_criteria_valid() -> None:
    errors = validate_search_criteria(
        interval_start="08:00",
        interval_end="18:00",
        days=["monday", "wednesday"],
        participant_ids=["u1", "u2"],
        duration_hours=2,
    )
    assert errors == {}


def test_validate_search_criteria_invalid_interval() -> None:
    errors = validate_search_criteria(
        interval_start="18:00",
        interval_end="08:00",
        days=["monday"],
        participant_ids=["u1"],
        duration_hours=1,
    )
    assert errors["interval"] == messages.INVALID_TIME_INTERVAL


def test_validate_search_criteria_no_days() -> None:
    errors = validate_search_criteria(
        interval_start="08:00",
        interval_end="18:00",
        days=[],
        participant_ids=["u1"],
        duration_hours=1,
    )
    assert errors["days"] == messages.SELECT_AT_LEAST_ONE_DAY


def test_validate_search_criteria_no_participants() -> None:
    errors = validate_search_criteria(
        interval_start="08:00",
        interval_end="18:00",
        days=["monday"],
        participant_ids=[],
        duration_hours=1,
    )
    assert errors["participants"] == messages.SELECT_AT_LEAST_ONE_PARTICIPANT


def test_validate_search_criteria_duration_not_whole() -> None:
    errors = validate_search_criteria(
        interval_start="08:00",
        interval_end="18:00",
        days=["monday"],
        participant_ids=["u1"],
        duration_hours=0,
    )
    assert errors["duration"] == messages.DURATION_WHOLE_HOURS


def test_validate_search_criteria_duration_exceeds_interval() -> None:
    errors = validate_search_criteria(
        interval_start="09:00",
        interval_end="11:00",
        days=["monday"],
        participant_ids=["u1"],
        duration_hours=3,
    )
    assert errors["duration"] == messages.DURATION_EXCEEDS_INTERVAL


def test_get_dates_for_week() -> None:
    # 2026-10-12 is Monday
    dates = get_dates_for_week("2026-10-12")
    assert dates["monday"] == "2026-10-12"
    assert dates["tuesday"] == "2026-10-13"
    assert dates["sunday"] == "2026-10-18"
