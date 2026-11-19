"""DevOps practices use cases with fakes."""

from typing import cast

import pytest

from app.modules.auth.domain.entities import User, UserRole
from app.modules.auth.domain.ports import UserRepository
from app.modules.devops.application.dtos import UpsertDevOpsProfileRequest
from app.modules.devops.application.use_cases import (
    GetProjectDevOpsProfileUseCase,
    UpsertProjectDevOpsProfileUseCase,
)
from app.modules.devops.domain.entities import DevOpsRevision, ProjectDevOpsProfile
from app.modules.devops.domain.ports import DevOpsProfileRepository
from app.modules.projects.domain.ports import ProjectRepository
from app.shared.application.identity import CurrentUser
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError
from tests.fakes import T0, FakeClock, FakeIdGenerator, FakeUnitOfWork


class _FakeProjects:
    def __init__(self, *, exists: bool, access: bool) -> None:
        self._exists = exists
        self._access = access

    def get_by_id(self, project_id: str) -> object | None:
        return object() if self._exists else None

    def user_can_access(self, project_id: str, user_id: str, role: str) -> bool:
        return self._access


class _FakeProfiles:
    def __init__(self) -> None:
        self.saved: ProjectDevOpsProfile | None = None
        self.revisions: list[DevOpsRevision] = []

    def get_by_project_id(self, project_id: str) -> ProjectDevOpsProfile | None:
        if self.saved and self.saved.project_id == project_id:
            return self.saved
        return None

    def save(self, profile: ProjectDevOpsProfile) -> None:
        self.saved = profile

    def add_revision(self, revision: DevOpsRevision) -> None:
        self.revisions.append(revision)

    def list_revisions(self, project_id: str, *, limit: int, offset: int) -> list[DevOpsRevision]:
        return self.revisions[offset : offset + limit]


class _FakeUsers:
    def get_by_id(self, user_id: str) -> User | None:
        return User(
            id=user_id,
            email="ana@b.io",
            hashed_password="hash",
            name="Ana",
            role=UserRole.DEVELOPER,
            is_active=True,
            created_at=T0,
            updated_at=T0,
        )


def test_get_empty_without_db_write() -> None:
    profiles = _FakeProfiles()
    use_case = GetProjectDevOpsProfileUseCase(
        profiles=cast(DevOpsProfileRepository, profiles),
        projects=cast(ProjectRepository, _FakeProjects(exists=True, access=True)),
        users=cast(UserRepository, _FakeUsers()),
    )
    actor = CurrentUser(
        id="m1",
        email="m@b.io",
        role="manager",
        name="Mgr",
        is_active=True,
        created_at=T0,
    )
    result = use_case.execute("proj", actor)
    assert result.is_configured is False
    assert profiles.saved is None


def test_upsert_creates_revision() -> None:
    profiles = _FakeProfiles()
    use_case = UpsertProjectDevOpsProfileUseCase(
        profiles=cast(DevOpsProfileRepository, profiles),
        projects=cast(ProjectRepository, _FakeProjects(exists=True, access=True)),
        users=cast(UserRepository, _FakeUsers()),
        clock=FakeClock(T0),
        id_gen=FakeIdGenerator("rev-1"),
        uow=FakeUnitOfWork(),
    )
    payload = UpsertDevOpsProfileRequest(
        change_summary="Alta inicial",
        repository_url="https://github.com/acme/x",
    )
    actor = CurrentUser(
        id="m1",
        email="m@b.io",
        role="manager",
        name="Mgr",
        is_active=True,
        created_at=T0,
    )
    result = use_case.execute("proj", payload, actor)
    assert result.is_configured is True
    assert len(profiles.revisions) == 1


def test_developer_cannot_upsert() -> None:
    use_case = UpsertProjectDevOpsProfileUseCase(
        profiles=cast(DevOpsProfileRepository, _FakeProfiles()),
        projects=cast(ProjectRepository, _FakeProjects(exists=True, access=True)),
        users=cast(UserRepository, _FakeUsers()),
        clock=FakeClock(T0),
        id_gen=FakeIdGenerator("x"),
        uow=FakeUnitOfWork(),
    )
    actor = CurrentUser(
        id="d1",
        email="d@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    with pytest.raises(AccessDeniedError):
        use_case.execute(
            "proj",
            UpsertDevOpsProfileRequest(change_summary="x"),
            actor,
        )


def test_upsert_rejects_no_changes() -> None:
    profiles = _FakeProfiles()
    existing = ProjectDevOpsProfile(
        id="p1",
        project_id="proj",
        repository_url=None,
        ci_cd_provider=None,
        branching_strategy=None,
        branching_rules_md=None,
        created_at=T0,
        updated_at=T0,
    )
    profiles.saved = existing
    use_case = UpsertProjectDevOpsProfileUseCase(
        profiles=cast(DevOpsProfileRepository, profiles),
        projects=cast(ProjectRepository, _FakeProjects(exists=True, access=True)),
        users=cast(UserRepository, _FakeUsers()),
        clock=FakeClock(T0),
        id_gen=FakeIdGenerator("x"),
        uow=FakeUnitOfWork(),
    )
    actor = CurrentUser(
        id="m1",
        email="m@b.io",
        role="manager",
        name="Mgr",
        is_active=True,
        created_at=T0,
    )
    with pytest.raises(AppError) as err:
        use_case.execute(
            "proj",
            UpsertDevOpsProfileRequest(change_summary="sin cambios"),
            actor,
        )
    assert err.value.code == "NO_CHANGES"
