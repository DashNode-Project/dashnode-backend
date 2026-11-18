"""Health indicator calculations for project summary (HU_DN_02_31)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectHealthSnapshot:
    completed_story_points: int
    total_story_points: int
    velocity_points_per_sprint: float
    open_issues: int
    user_stories_count: int = 0
    user_stories_completed_count: int = 0
    tasks_count: int = 0
    tasks_completed_count: int = 0


@dataclass(frozen=True)
class ProjectHealthIndicators:
    progress_percent: float
    velocity: float
    open_issues: int
    user_stories_count: int
    user_stories_completed_count: int
    tasks_count: int
    tasks_completed_count: int
    completed_story_points: int
    total_story_points: int


def compute_health_indicators(snapshot: ProjectHealthSnapshot) -> ProjectHealthIndicators:
    if snapshot.total_story_points <= 0:
        progress = 0.0
    else:
        progress = (snapshot.completed_story_points / snapshot.total_story_points) * 100.0
    return ProjectHealthIndicators(
        progress_percent=round(progress, 2),
        velocity=round(snapshot.velocity_points_per_sprint, 2),
        open_issues=max(snapshot.open_issues, 0),
        user_stories_count=max(snapshot.user_stories_count, 0),
        user_stories_completed_count=max(snapshot.user_stories_completed_count, 0),
        tasks_count=max(snapshot.tasks_count, 0),
        tasks_completed_count=max(snapshot.tasks_completed_count, 0),
        completed_story_points=max(snapshot.completed_story_points, 0),
        total_story_points=max(snapshot.total_story_points, 0),
    )
