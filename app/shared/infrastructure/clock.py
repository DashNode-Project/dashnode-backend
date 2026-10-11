"""
System clock implementation fulfilling the Clock port.
@sad AD-09
@origin [SAD-Propuesto]
"""

from datetime import UTC, datetime

from app.shared.application.ports import Clock


class SystemClock(Clock):
    """Real clock using timezone-aware UTC datetime."""

    def now(self) -> datetime:
        return datetime.now(UTC)  # noqa: TID251
