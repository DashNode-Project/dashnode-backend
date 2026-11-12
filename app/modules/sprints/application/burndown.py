"""Burndown ideal vs. actual remaining points by sprint day (HU_DN_05_68)."""

from datetime import date, timedelta

from app.modules.backlog.domain.entities import StoryTask, UserStory
from app.modules.sprints.application.metrics import story_effective_points, story_is_completed


def iter_sprint_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def story_completion_date(
    story: UserStory,
    tasks: list[StoryTask],
    done_at_by_task: dict[str, date],
) -> date | None:
    if not story_is_completed(story, tasks):
        return None
    story_tasks = [t for t in tasks if t.user_story_id == story.id]
    dates = [done_at_by_task[t.id] for t in story_tasks if t.id in done_at_by_task]
    if len(dates) < len(story_tasks):
        fallback = max((t.updated_at.date() for t in story_tasks), default=None)
        return fallback
    return max(dates)


def build_ideal_line(total: int, start: date, end: date) -> list[dict[str, object]]:
    days = iter_sprint_days(start, end)
    if not days:
        return []
    if len(days) == 1:
        return [
            {"date": days[0].isoformat(), "points": total},
        ]
    span = len(days) - 1
    line: list[dict[str, object]] = []
    for index, day in enumerate(days):
        remaining = round(total * (1 - index / span))
        line.append({"date": day.isoformat(), "points": remaining})
    line[-1]["points"] = 0
    line[0]["points"] = total
    return line


def build_actual_line(
    total: int,
    start: date,
    end: date,
    stories: list[UserStory],
    tasks: list[StoryTask],
    done_at_by_task: dict[str, date],
) -> list[dict[str, object]]:
    days = iter_sprint_days(start, end)
    line: list[dict[str, object]] = []
    for day in days:
        burned = 0
        for story in stories:
            completed_on = story_completion_date(story, tasks, done_at_by_task)
            if completed_on is not None and completed_on <= day:
                burned += story_effective_points(story, tasks)
        remaining = max(total - burned, 0)
        line.append({"date": day.isoformat(), "points": remaining})
    return line
