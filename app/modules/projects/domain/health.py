"""Health indicator calculations for project summary (HU_DN_02_31)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectHealthSnapshot:
    completed_story_points: int
    total_story_points: int
    velocity_points_per_sprint: float
    open_issues: int


@dataclass(frozen=True)
class ProjectHealthIndicators:
    progress_percent: float
    velocity: float
    open_issues: int


def compute_health_indicators(snapshot: ProjectHealthSnapshot) -> ProjectHealthIndicators:
    if snapshot.total_story_points <= 0:
        progress = 0.0
    else:
        progress = (snapshot.completed_story_points / snapshot.total_story_points) * 100.0
    return ProjectHealthIndicators(
        progress_percent=round(progress, 2),
        velocity=round(snapshot.velocity_points_per_sprint, 2),
        open_issues=max(snapshot.open_issues, 0),
    )
