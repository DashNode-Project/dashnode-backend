"""Unit tests for sprint burndown calculations (HU_DN_05_68)."""

from datetime import date

from app.modules.backlog.domain.entities import (
    EstimationMode,
    MoscowPriority,
    StoryTask,
    StoryTaskStatus,
    StoryTaskType,
    UserStory,
)
from app.modules.sprints.application.burndown import build_actual_line, build_ideal_line


def _story(story_id: str, sprint_id: str, points: int = 8) -> UserStory:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return UserStory(
        id=story_id,
        epic_id="e1",
        project_id="p1",
        title="HU",
        user_role="dev",
        reason="r",
        acceptance_criteria="",
        moscow_priority=MoscowPriority.MUST_HAVE,
        story_points=points,
        estimation_mode=EstimationMode.STORY,
        sprint_id=sprint_id,
        sort_order=0,
        created_by="u1",
        created_at=now,
        updated_at=now,
    )


def _task(task_id: str, story_id: str) -> StoryTask:
    from datetime import UTC, datetime
    from decimal import Decimal

    now = datetime.now(UTC)
    return StoryTask(
        id=task_id,
        user_story_id=story_id,
        project_id="p1",
        name="T",
        task_type=StoryTaskType.BACKEND,
        notes="",
        status=StoryTaskStatus.DONE,
        assignee_id=None,
        estimated_hours=None,
        created_by="u1",
        created_at=now,
        updated_at=now,
        story_points=None,
        logged_hours=Decimal("0"),
        label="",
    )


def test_ideal_line_goes_from_total_to_zero() -> None:
    line = build_ideal_line(20, date(2026, 11, 1), date(2026, 11, 5))
    assert line[0]["points"] == 20
    assert line[-1]["points"] == 0


def test_actual_line_constant_without_completions() -> None:
    story = _story("s1", "sp1", 10)
    line = build_actual_line(
        10,
        date(2026, 11, 1),
        date(2026, 11, 3),
        [story],
        [],
        {},
    )
    assert all(row["points"] == 10 for row in line)
