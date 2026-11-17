"""UTC period windows for EP-13 metrics queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.modules.ai_metrics.domain import messages as iam_msg
from app.shared.domain.errors import AppError, ErrorKind


@dataclass(frozen=True, slots=True)
class MetricsPeriod:
    key: str
    start: datetime
    end: datetime


def _start_of_utc_day(moment: datetime) -> datetime:
    m = moment.astimezone(UTC)
    return m.replace(hour=0, minute=0, second=0, microsecond=0)


def parse_metrics_period(
    period: str | None,
    *,
    from_iso: str | None,
    to_iso: str | None,
    now: datetime,
) -> MetricsPeriod:
    key = (period or "30d").strip().lower()
    end = now.astimezone(UTC)

    if key == "today":
        return MetricsPeriod(key="today", start=_start_of_utc_day(end), end=end)
    if key == "7d":
        return MetricsPeriod(key="7d", start=end - timedelta(days=7), end=end)
    if key == "30d":
        return MetricsPeriod(key="30d", start=end - timedelta(days=30), end=end)
    if key == "month":
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return MetricsPeriod(key="month", start=start, end=end)
    if key == "custom":
        if not from_iso or not to_iso:
            raise AppError(
                "INVALID_METRICS_PERIOD",
                iam_msg.AI_METRICS_PERIOD_INVALID,
                ErrorKind.VALIDATION,
            )
        start = datetime.fromisoformat(from_iso.replace("Z", "+00:00")).astimezone(UTC)
        stop = datetime.fromisoformat(to_iso.replace("Z", "+00:00")).astimezone(UTC)
        if stop < start:
            raise AppError(
                "INVALID_METRICS_PERIOD",
                iam_msg.AI_METRICS_PERIOD_INVALID,
                ErrorKind.VALIDATION,
            )
        return MetricsPeriod(key="custom", start=start, end=stop)

    raise AppError(
        "INVALID_METRICS_PERIOD",
        iam_msg.AI_METRICS_PERIOD_INVALID,
        ErrorKind.VALIDATION,
    )
