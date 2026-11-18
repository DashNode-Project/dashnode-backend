"""Project default timezone (EP-13 meetings, EP-14 templates)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

PROJECT_TIMEZONE = ZoneInfo("America/Bogota")


def project_local_ymd_hm(when: datetime) -> tuple[str, str]:
    """Return (YYYY-MM-DD, HH:MM) in America/Bogota."""
    local = when.astimezone(PROJECT_TIMEZONE)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")


def project_local_date(when: datetime) -> date:
    """Calendar date in project timezone."""
    return when.astimezone(PROJECT_TIMEZONE).date()
