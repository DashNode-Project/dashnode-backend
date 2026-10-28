"""Unit tests for Kanban rules and domain entities (EP-08)."""

from datetime import UTC, datetime
from decimal import Decimal

from app.modules.backlog.domain.entities import (
    EstimationMode,
    MoscowPriority,
    StoryTask,
    StoryTaskStatus,
    StoryTaskType,
    UserStory,
)
from app.modules.kanban.application.use_cases import GetKanbanBoardUseCase
from app.modules.kanban.domain.entities import STANDARD_COLUMNS
from app.modules.sprints.domain.entities import Sprint, SprintStatus
from app.shared.application.identity import CurrentUser


class InMemoryKanbanRepo:
    def __init__(self) -> None:
        self.limits: dict[str, int | None] = {}

    def get_wip_limits(self, project_id: str) -> dict[str, int | None]:
        return dict(self.limits)

    def set_wip_limit(
        self,
        new_id: str,
        project_id: str,
        column_id: str,
        wip_limit: int | None,
        when: datetime,
    ) -> None:
        self.limits[column_id] = wip_limit


class InMemorySprintRepo:
    def __init__(self, active_sprint: Sprint | None = None) -> None:
        self.active_sprint = active_sprint

    def get_active_for_project(self, project_id: str) -> Sprint | None:
        return self.active_sprint


class InMemoryBacklogRepo:
    def __init__(self, stories: list[UserStory], tasks: list[StoryTask]) -> None:
        self.stories = stories
        self.tasks = tasks

    def list_stories_by_project(self, project_id: str) -> list[UserStory]:
        return [s for s in self.stories if s.project_id == project_id]

    def list_tasks_by_project(self, project_id: str) -> list[StoryTask]:
        return [t for t in self.tasks if t.project_id == project_id]

    def get_story_task(self, task_id: str) -> StoryTask | None:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def update_story_task(self, task: StoryTask) -> None:
        for idx, t in enumerate(self.tasks):
            if t.id == task.id:
                self.tasks[idx] = task
                return


class MockProject:
    def __init__(self, project_id: str, manager_id: str = "mgr-1") -> None:
        self.id = project_id
        self.name = "Test Project"
        self.manager_id = manager_id

    def is_deleted(self) -> bool:
        return False


class MockProjectLookup:
    def __init__(self, project: MockProject) -> None:
        self.project = project

    def get_project(self, project_id: str) -> MockProject | None:
        if self.project.id == project_id:
            return self.project
        return None

    def is_member(self, project_id: str, user_id: str) -> bool:
        return True


class MockUserLookup:
    def get_user_display(self, user_id: str) -> tuple[str, str | None] | None:
        return (f"User {user_id}", None)


def test_standard_columns_order_and_ids() -> None:
    expected_ids = ["TODO", "IN_PROGRESS", "CODE_REVIEW", "TESTING", "CORRECTION", "DONE"]
    assert [col_id.value for col_id, _ in STANDARD_COLUMNS] == expected_ids
    assert len(STANDARD_COLUMNS) == 6


def test_developer_role_filters_to_own_tasks_only() -> None:
    now = datetime.now(UTC)
    active_sprint = Sprint(
        id="sprint-1",
        project_id="proj-1",
        name="Sprint 1",
        goal="Objetivo",
        start_date=now.date(),
        end_date=now.date(),
        status=SprintStatus.ACTIVE,
        created_at=now,
    )
    story = UserStory(
        id="story-1",
        epic_id="epic-1",
        project_id="proj-1",
        title="HU 1",
        user_role="User",
        reason="Reason",
        acceptance_criteria="AC",
        moscow_priority=MoscowPriority.MUST_HAVE,
        story_points=5,
        estimation_mode=EstimationMode.STORY,
        sprint_id="sprint-1",
        sort_order=0,
        created_by="mgr-1",
        created_at=now,
        updated_at=now,
        label="HU-01",
    )
    task_dev = StoryTask(
        id="task-1",
        user_story_id="story-1",
        project_id="proj-1",
        name="Dev Task",
        task_type=StoryTaskType.FRONTEND,
        notes="",
        status=StoryTaskStatus.TODO,
        assignee_id="dev-1",
        estimated_hours=Decimal("4"),
        created_by="mgr-1",
        created_at=now,
        updated_at=now,
    )
    task_other = StoryTask(
        id="task-2",
        user_story_id="story-1",
        project_id="proj-1",
        name="Other Task",
        task_type=StoryTaskType.BACKEND,
        notes="",
        status=StoryTaskStatus.TODO,
        assignee_id="dev-2",
        estimated_hours=Decimal("6"),
        created_by="mgr-1",
        created_at=now,
        updated_at=now,
    )

    use_case = GetKanbanBoardUseCase(
        sprints=InMemorySprintRepo(active_sprint),
        backlog=InMemoryBacklogRepo([story], [task_dev, task_other]),
        kanban=InMemoryKanbanRepo(),
        projects=MockProjectLookup(MockProject("proj-1")),
        users=MockUserLookup(),
    )

    dev_actor = CurrentUser(
        id="dev-1",
        email="dev@test.com",
        name="Dev One",
        role="developer",
        is_active=True,
        created_at=now,
    )
    res_dev = use_case.execute("proj-1", dev_actor)
    todo_col_dev = next(c for c in res_dev.columns if c.id == "TODO")
    assert len(todo_col_dev.cards) == 1
    assert todo_col_dev.cards[0].id == "task-1"

    mgr_actor = CurrentUser(
        id="mgr-1",
        email="mgr@test.com",
        name="Mgr One",
        role="manager",
        is_active=True,
        created_at=now,
    )
    res_mgr = use_case.execute("proj-1", mgr_actor)
    todo_col_mgr = next(c for c in res_mgr.columns if c.id == "TODO")
    assert len(todo_col_mgr.cards) == 2


def test_effective_blockage_resolution() -> None:
    now = datetime.now(UTC)
    active_sprint = Sprint(
        id="sprint-1",
        project_id="proj-1",
        name="Sprint 1",
        goal=None,
        start_date=now.date(),
        end_date=now.date(),
        status=SprintStatus.ACTIVE,
        created_at=now,
    )
    story = UserStory(
        id="story-1",
        epic_id="epic-1",
        project_id="proj-1",
        title="HU 1",
        user_role="User",
        reason="Reason",
        acceptance_criteria="AC",
        moscow_priority=MoscowPriority.MUST_HAVE,
        story_points=3,
        estimation_mode=EstimationMode.STORY,
        sprint_id="sprint-1",
        sort_order=0,
        created_by="mgr-1",
        created_at=now,
        updated_at=now,
    )
    predecessor = StoryTask(
        id="task-dep",
        user_story_id="story-1",
        project_id="proj-1",
        name="Predecessor Task",
        task_type=StoryTaskType.BACKEND,
        notes="",
        status=StoryTaskStatus.IN_PROGRESS,
        assignee_id="dev-1",
        estimated_hours=Decimal("2"),
        created_by="mgr-1",
        created_at=now,
        updated_at=now,
    )
    dependent = StoryTask(
        id="task-main",
        user_story_id="story-1",
        project_id="proj-1",
        name="Main Task",
        task_type=StoryTaskType.FRONTEND,
        notes="",
        status=StoryTaskStatus.TODO,
        assignee_id="dev-1",
        estimated_hours=Decimal("4"),
        created_by="mgr-1",
        created_at=now,
        updated_at=now,
        blocked_by_task_id="task-dep",
    )

    use_case = GetKanbanBoardUseCase(
        sprints=InMemorySprintRepo(active_sprint),
        backlog=InMemoryBacklogRepo([story], [predecessor, dependent]),
        kanban=InMemoryKanbanRepo(),
        projects=MockProjectLookup(MockProject("proj-1")),
        users=MockUserLookup(),
    )

    res = use_case.execute(
        "proj-1",
        CurrentUser(
            id="mgr-1",
            email="m@t.com",
            name="Mgr One",
            role="manager",
            is_active=True,
            created_at=now,
        ),
    )
    todo_col = next(c for c in res.columns if c.id == "TODO")
    main_card = next(c for c in todo_col.cards if c.id == "task-main")
    assert main_card.is_blocked is True
    assert "Predecessor Task" in (main_card.blocked_reason or "")
