"""
Application tests for Projects use cases.
@sad AD-09, 4.1.2
"""

from datetime import UTC, datetime

import pytest

from app.modules.projects.application.dtos import AddMemberCommand, CreateProjectCommand
from app.modules.projects.application.use_cases import (
    AddProjectMemberUseCase,
    CreateProjectUseCase,
    GetProjectHealthUseCase,
    GetProjectUseCase,
    ListProjectsUseCase,
    RemoveProjectMemberUseCase,
)
from app.modules.projects.domain.entities import (
    Project,
    ProjectMember,
    ProjectPriority,
    ProjectStatus,
)
from app.modules.projects.domain.health import ProjectHealthSnapshot, compute_health_indicators
from app.modules.projects.domain.messages import MEMBER_ADDED
from app.modules.projects.domain.ports import MemberProfile
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import UnitOfWork


class FakeManagerLookup:
    def __init__(self, valid_ids: set[str]) -> None:
        self._valid = valid_ids

    def is_active_manager(self, user_id: str) -> bool:
        return user_id in self._valid


class FakeProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.members: list[ProjectMember] = []

    def get_by_id(self, project_id: str) -> Project | None:
        project = self.projects.get(project_id)
        if project is None or project.is_deleted():
            return None
        return project

    def list_visible_for_user(self, user_id: str, *, role: str) -> list[Project]:
        member_proj_ids = {m.project_id for m in self.members if m.user_id == user_id}
        visible: list[Project] = []
        for project in self.projects.values():
            if project.is_deleted():
                continue
            if (
                role == "admin"
                or (
                    role == "manager"
                    and (project.manager_id == user_id or project.id in member_proj_ids)
                )
                or project.id in member_proj_ids
            ):
                visible.append(project)
        return visible

    def save(self, project: Project) -> None:
        self.projects[project.id] = project

    def update(self, project: Project) -> None:
        self.projects[project.id] = project

    def add_member(self, member: ProjectMember) -> None:
        if not self.is_member(member.project_id, member.user_id):
            self.members.append(member)

    def get_members(self, project_id: str) -> list[ProjectMember]:
        return [m for m in self.members if m.project_id == project_id]

    def is_member(self, project_id: str, user_id: str) -> bool:
        return any(m.project_id == project_id and m.user_id == user_id for m in self.members)

    def user_can_access(self, project_id: str, user_id: str, role: str) -> bool:
        if self.get_by_id(project_id) is None:
            return False
        return any(p.id == project_id for p in self.list_visible_for_user(user_id, role=role))

    def soft_delete_cascade(self, project_id: str, when: datetime) -> None:
        project = self.projects.get(project_id)
        if project:
            project.deleted_at = when

    def add_audit_entry(self, **kwargs: object) -> None:
        return None

    def remove_member(self, project_id: str, user_id: str) -> None:
        self.members = [
            m for m in self.members if not (m.project_id == project_id and m.user_id == user_id)
        ]

    def clear_assignee_tasks(self, project_id: str, user_id: str, *, when: datetime) -> None:
        return None

    def get_health_snapshot(self, project_id: str) -> ProjectHealthSnapshot:
        return ProjectHealthSnapshot(0, 0, 0.0, 0)


class FakeActiveUserLookup:
    def __init__(self, profiles: dict[str, MemberProfile]) -> None:
        self._profiles = profiles

    def is_active_user(self, user_id: str) -> bool:
        return user_id in self._profiles

    def display_name(self, user_id: str) -> str | None:
        profile = self._profiles.get(user_id)
        return profile.name if profile else None

    def get_member_profile(self, user_id: str) -> MemberProfile | None:
        return self._profiles.get(user_id)

    def list_active_users(self, *, query: str = "") -> list[MemberProfile]:
        rows = list(self._profiles.values())
        if query.strip():
            q = query.strip().lower()
            rows = [p for p in rows if q in p.name.lower() or q in p.email.lower()]
        return rows


class FakeClock:
    def __init__(self, now_time: datetime) -> None:
        self._now = now_time

    def now(self) -> datetime:
        return self._now


class FakeIdGenerator:
    def __init__(self, fixed_id: str = "proj-100") -> None:
        self.fixed_id = fixed_id

    def generate(self) -> str:
        return self.fixed_id


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


def _project(
    *,
    id: str = "proj-1",
    name: str = "Test",
    description: str = "",
    owner_id: str = "owner-id",
    manager_id: str = "owner-id",
    priority: ProjectPriority = ProjectPriority.MEDIA,
    tech_stack: list[str] | None = None,
    meeting_link: str | None = None,
    status: ProjectStatus = ProjectStatus.PLANIFICACION,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Project:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return Project(
        id=id,
        name=name,
        description=description,
        owner_id=owner_id,
        manager_id=manager_id,
        priority=priority,
        tech_stack=tech_stack or [],
        meeting_link=meeting_link,
        status=status,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def test_create_project_use_case() -> None:
    repo = FakeProjectRepository()
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    clock = FakeClock(now)
    uow = FakeUnitOfWork()

    use_case = CreateProjectUseCase(
        project_repo=repo,
        manager_lookup=FakeManagerLookup({"mgr-1"}),
        id_gen=FakeIdGenerator("proj-999"),
        clock=clock,
        uow=uow,
    )

    actor = CurrentUser(
        id="mgr-1",
        email="m@example.com",
        name="Mgr",
        role="manager",
        is_active=True,
        created_at=now,
    )
    cmd = CreateProjectCommand(name="DashNode Platform", description="Main", manager_id="mgr-1")
    result = use_case.execute(cmd=cmd, actor=actor)

    assert result.id == "proj-999"
    assert result.manager_id == "mgr-1"
    assert uow.committed is True
    assert repo.is_member("proj-999", "mgr-1") is True


def test_add_project_member_success() -> None:
    repo = FakeProjectRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    uow = FakeUnitOfWork()
    repo.save(_project())
    users = FakeActiveUserLookup(
        {
            "dev-1": MemberProfile("dev-1", "Dev", "dev@t.com", "developer"),
        }
    )
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    actor = CurrentUser(
        id="owner-id",
        email="o@x.com",
        name="O",
        role="manager",
        is_active=True,
        created_at=now,
    )

    use_case = AddProjectMemberUseCase(project_repo=repo, users=users, clock=clock, uow=uow)
    cmd = AddMemberCommand(user_id="dev-1")

    result = use_case.execute(project_id="proj-1", cmd=cmd, actor=actor)
    assert result.message == MEMBER_ADDED
    assert repo.is_member("proj-1", "dev-1")
    assert uow.committed is True


def test_add_project_member_unauthorized() -> None:
    repo = FakeProjectRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    uow = FakeUnitOfWork()
    repo.save(_project())
    users = FakeActiveUserLookup({"dev-1": MemberProfile("dev-1", "Dev", "dev@t.com", "developer")})
    use_case = AddProjectMemberUseCase(project_repo=repo, users=users, clock=clock, uow=uow)
    cmd = AddMemberCommand(user_id="dev-1")
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    from app.shared.domain.authorization import AccessDeniedError

    stranger = CurrentUser(
        id="stranger-id",
        email="x@x.com",
        name="X",
        role="developer",
        is_active=True,
        created_at=now,
    )
    with pytest.raises(AccessDeniedError):
        use_case.execute(project_id="proj-1", cmd=cmd, actor=stranger)


def test_remove_project_member_blocks_manager() -> None:
    repo = FakeProjectRepository()
    uow = FakeUnitOfWork()
    repo.save(_project())
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    actor = CurrentUser(
        id="owner-id",
        email="o@x.com",
        name="O",
        role="manager",
        is_active=True,
        created_at=now,
    )
    use_case = RemoveProjectMemberUseCase(
        project_repo=repo, clock=FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)), uow=uow
    )
    from app.shared.domain.errors import AppError

    with pytest.raises(AppError):
        use_case.execute(project_id="proj-1", member_user_id="owner-id", actor=actor)


def test_health_indicators_zero_without_data() -> None:
    repo = FakeProjectRepository()
    repo.save(_project())
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    actor = CurrentUser(
        id="owner-id",
        email="o@x.com",
        name="O",
        role="manager",
        is_active=True,
        created_at=now,
    )
    use_case = GetProjectHealthUseCase(project_repo=repo)
    health = use_case.execute("proj-1", actor)
    assert health.progress_percent == 0.0
    assert health.velocity == 0.0
    assert health.open_issues == 0


def test_compute_health_with_story_points() -> None:
    indicators = compute_health_indicators(
        ProjectHealthSnapshot(
            completed_story_points=5,
            total_story_points=20,
            velocity_points_per_sprint=8.5,
            open_issues=2,
        )
    )
    assert indicators.progress_percent == 25.0
    assert indicators.velocity == 8.5
    assert indicators.open_issues == 2


def test_list_and_get_projects() -> None:
    repo = FakeProjectRepository()
    repo.save(_project(id="proj-1", owner_id="owner-1", manager_id="owner-1"))
    users = FakeActiveUserLookup(
        {"owner-1": MemberProfile("owner-1", "Owner", "o@t.com", "manager")}
    )

    list_uc = ListProjectsUseCase(project_repo=repo, users=users)
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    actor = CurrentUser(
        id="owner-1",
        email="o@x.com",
        name="O",
        role="manager",
        is_active=True,
        created_at=now,
    )
    user_projects = list_uc.execute(actor)
    assert len(user_projects) == 1

    get_uc = GetProjectUseCase(project_repo=repo, users=users)
    p = get_uc.execute("proj-1", actor)
    assert p.id == "proj-1"

    from app.shared.domain.authorization import AccessDeniedError

    other = CurrentUser(
        id="other",
        email="x@x.com",
        name="X",
        role="developer",
        is_active=True,
        created_at=now,
    )
    with pytest.raises(AccessDeniedError):
        get_uc.execute("proj-1", other)
