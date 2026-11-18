"""Project timezone helpers."""

from datetime import UTC, datetime

from app.shared.infrastructure.project_local_time import project_local_date, project_local_ymd_hm


def test_project_local_ymd_hm_bogota() -> None:
    # 2026-11-18 02:30 UTC = 2026-11-17 21:30 Bogota
    when = datetime(2026, 11, 18, 2, 30, tzinfo=UTC)
    ymd, hm = project_local_ymd_hm(when)
    assert ymd == "2026-11-17"
    assert hm == "21:30"


def test_project_local_date_bogota() -> None:
    when = datetime(2026, 11, 18, 2, 30, tzinfo=UTC)
    assert project_local_date(when).isoformat() == "2026-11-17"
