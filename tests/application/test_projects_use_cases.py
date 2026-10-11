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
from app.modules.projects.domain.entities import Project, ProjectMember, ProjectRole
from app.shared.application.ports import UnitOfWork


class FakeProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.members: list[ProjectMember] = []

    def get_by_id(self, project_id: str) -> Project | None:
        return self.projects.get(project_id)

    def list_by_user(self, user_id: str) -> list[Project]:
        member_proj_ids = {m.project_id for m in self.members if m.user_id == user_id}
        return [
            p for p in self.projects.values()
            if p.owner_id == user_id or p.id in member_proj_ids
        ]

    def save(self, project: Project) -> None:
        self.projects[project.id] = project

    def update(self, project: Project) -> None:
        self.projects[project.id] = project

    def add_member(self, member: ProjectMember) -> None:
        self.members.append(member)

    def get_members(self, project_id: str) -> list[ProjectMember]:
        return [m for m in self.members if m.project_id == project_id]

    def is_member(self, project_id: str, user_id: str) -> bool:
        return any(m.project_id == project_id and m.user_id == user_id for m in self.members)


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


def test_create_project_use_case() -> None:
    repo = FakeProjectRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    id_gen = FakeIdGenerator("proj-999")
    uow = FakeUnitOfWork()

    use_case = CreateProjectUseCase(
        project_repo=repo,
        id_gen=id_gen,
        clock=clock,
        uow=uow,
    )

    cmd = CreateProjectCommand(name="DashNode Platform", description="Main platform")
    result = use_case.execute(cmd=cmd, owner_id="user-owner-1")

    assert result.id == "proj-999"
    assert result.name == "DashNode Platform"
    assert result.owner_id == "user-owner-1"
    assert uow.committed is True

    # Owner should be added as lead member
    assert repo.is_member("proj-999", "user-owner-1") is True


def test_add_project_member_success() -> None:
    repo = FakeProjectRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    uow = FakeUnitOfWork()

    project = Project(
        id="proj-1",
        name="Test",
        description="",
        owner_id="owner-id",
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    repo.save(project)

    use_case = AddProjectMemberUseCase(project_repo=repo, clock=clock, uow=uow)
    cmd = AddMemberCommand(user_id="dev-1", role=ProjectRole.MEMBER)

    member_dto = use_case.execute(project_id="proj-1", cmd=cmd, actor_id="owner-id")
    assert member_dto.user_id == "dev-1"
    assert member_dto.role == ProjectRole.MEMBER
    assert uow.committed is True


def test_add_project_member_unauthorized() -> None:
    repo = FakeProjectRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    uow = FakeUnitOfWork()

    project = Project(
        id="proj-1",
        name="Test",
        description="",
        owner_id="owner-id",
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    repo.save(project)

    use_case = AddProjectMemberUseCase(project_repo=repo, clock=clock, uow=uow)
    cmd = AddMemberCommand(user_id="dev-1", role=ProjectRole.MEMBER)

    with pytest.raises(ValueError, match="No tienes permisos"):
        use_case.execute(project_id="proj-1", cmd=cmd, actor_id="stranger-id")


def test_list_and_get_projects() -> None:
    repo = FakeProjectRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))

    project = Project(
        id="proj-1",
        name="Project One",
        description="",
        owner_id="owner-1",
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    repo.save(project)

    list_uc = ListProjectsUseCase(project_repo=repo)
    user_projects = list_uc.execute("owner-1")
    assert len(user_projects) == 1
    assert user_projects[0].name == "Project One"

    get_uc = GetProjectUseCase(project_repo=repo)
    p = get_uc.execute("proj-1", "owner-1")
    assert p.id == "proj-1"

    # Unauthorized get
    with pytest.raises(ValueError, match="No tienes acceso"):
        get_uc.execute("proj-1", "other-user")
