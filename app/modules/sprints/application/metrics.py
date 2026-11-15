"""Sprint point and progress calculations (HU_DN_05_67)."""

from datetime import date

from app.modules.backlog.domain.entities import (
    EstimationMode,
    StoryTask,
    StoryTaskStatus,
    UserStory,
)


def story_effective_points(story: UserStory, tasks: list[StoryTask]) -> int:
    if story.estimation_mode == EstimationMode.TASK:
        return sum(t.story_points or 0 for t in tasks if t.user_story_id == story.id)
    return story.story_points or 0


def story_is_completed(story: UserStory, tasks: list[StoryTask]) -> bool:
    story_tasks = [t for t in tasks if t.user_story_id == story.id]
    if not story_tasks:
        return False
    return all(t.status == StoryTaskStatus.DONE for t in story_tasks)


def compute_sprint_points(
    stories: list[UserStory], tasks: list[StoryTask], sprint_id: str
) -> tuple[int, int, int]:
    in_sprint = [s for s in stories if s.sprint_id == sprint_id]
    total = 0
    completed = 0
    for story in in_sprint:
        pts = story_effective_points(story, tasks)
        total += pts
        if story_is_completed(story, tasks):
            completed += pts
    pending = max(total - completed, 0)
    return total, completed, pending


def progress_percentage(total: int, completed: int) -> float:
    if total <= 0:
        return 0.0
    return round((completed / total) * 100.0, 1)


def days_remaining(end_date: date, today: date) -> int:
    return max((end_date - today).days, 0)
