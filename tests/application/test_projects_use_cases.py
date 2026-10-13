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
    GetProjectUseCase,
    ListProjectsUseCase,
)
from app.modules.projects.domain.entities import (
    Project,
    ProjectMember,
    ProjectPriority,
    ProjectRole,
    ProjectStatus,
)
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

    def soft_delete_cascade(self, project_id: str, when: datetime) -> None:
        project = self.projects.get(project_id)
        if project:
            project.deleted_at = when

    def add_audit_entry(self, **kwargs: object) -> None:
        return None


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


def _project(**overrides: object) -> Project:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    base = dict(
        id="proj-1",
        name="Test",
        description="",
        owner_id="owner-id",
        manager_id="owner-id",
        priority=ProjectPriority.MEDIA,
        tech_stack=[],
        meeting_link=None,
        status=ProjectStatus.PLANIFICACION,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return Project(**base)  # type: ignore[arg-type]


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

    use_case = AddProjectMemberUseCase(project_repo=repo, clock=clock, uow=uow)
    cmd = AddMemberCommand(user_id="dev-1", role=ProjectRole.MEMBER)

    member_dto = use_case.execute(project_id="proj-1", cmd=cmd, actor_id="owner-id")
    assert member_dto.user_id == "dev-1"
    assert uow.committed is True


def test_add_project_member_unauthorized() -> None:
    repo = FakeProjectRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    uow = FakeUnitOfWork()
    repo.save(_project())

    use_case = AddProjectMemberUseCase(project_repo=repo, clock=clock, uow=uow)
    cmd = AddMemberCommand(user_id="dev-1", role=ProjectRole.MEMBER)

    from app.shared.domain.authorization import AccessDeniedError

    with pytest.raises(AccessDeniedError):
        use_case.execute(project_id="proj-1", cmd=cmd, actor_id="stranger-id")


def test_list_and_get_projects() -> None:
    repo = FakeProjectRepository()
    repo.save(_project(id="proj-1", owner_id="owner-1", manager_id="owner-1"))

    list_uc = ListProjectsUseCase(project_repo=repo)
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

    get_uc = GetProjectUseCase(project_repo=repo)
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
