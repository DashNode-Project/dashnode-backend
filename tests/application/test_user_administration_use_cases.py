"""Unit tests for EP-02 user administration use cases."""

from datetime import timedelta

import pytest

from app.modules.auth.application.dtos import (
    CreateUserByAdminCommand,
    InviteDeveloperCommand,
    UpdateUserByAdminCommand,
)
from app.modules.auth.application.password_reset_use_cases import CredentialTokenPolicy
from app.modules.auth.application.user_administration_use_cases import (
    CreateUserByAdminUseCase,
    InviteDeveloperByManagerUseCase,
    ListAdminUsersUseCase,
    UpdateUserByAdminUseCase,
)
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import UserRole
from app.modules.auth.domain.errors import (
    EmailAlreadyRegisteredError,
    ManagerRoleChangeBlockedError,
)
from app.shared.domain.authorization import AccessDeniedError
from tests.fakes import (
    FakeClock,
    FakeIdGenerator,
    FakePasswordCredentialTokenRepository,
    FakePasswordHasher,
    FakeProjectOwnershipQuery,
    FakeSessionTokenService,
    FakeTransactionalEmailSender,
    FakeUnitOfWork,
    FakeUserRepository,
    make_user,
)


def _policy() -> CredentialTokenPolicy:
    return CredentialTokenPolicy(
        reset_ttl=timedelta(minutes=30),
        activation_ttl=timedelta(hours=24),
        frontend_base_url="http://localhost:8080",
    )


def test_admin_create_user_sends_activation() -> None:
    repo = FakeUserRepository()
    admin = make_user(user_id="admin-1", email="admin@x.com", role=UserRole.ADMIN, name="Admin")
    repo.save(admin)
    mailer = FakeTransactionalEmailSender()
    use_case = CreateUserByAdminUseCase(
        user_repo=repo,
        token_repo=FakePasswordCredentialTokenRepository(),
        tokens=FakeSessionTokenService(),
        mailer=mailer,
        hasher=FakePasswordHasher(),
        id_gen=FakeIdGenerator(),
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
        policy=_policy(),
    )
    result = use_case.execute(
        actor_id="admin-1",
        cmd=CreateUserByAdminCommand(name="Nuevo Dev", email="dev@empresa.com", role="developer"),
    )
    assert result.message == messages.USER_CREATED
    assert len(mailer.sent) == 1
    assert repo.get_by_email("dev@empresa.com") is not None


def test_create_user_rejects_admin_role() -> None:
    repo = FakeUserRepository()
    admin = make_user(user_id="admin-1", email="admin@x.com", role=UserRole.ADMIN)
    repo.save(admin)
    use_case = CreateUserByAdminUseCase(
        user_repo=repo,
        token_repo=FakePasswordCredentialTokenRepository(),
        tokens=FakeSessionTokenService(),
        mailer=FakeTransactionalEmailSender(),
        hasher=FakePasswordHasher(),
        id_gen=FakeIdGenerator(),
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
        policy=_policy(),
    )
    with pytest.raises(AccessDeniedError):
        use_case.execute(
            actor_id="admin-1",
            cmd=CreateUserByAdminCommand(name="X", email="x@x.com", role="admin"),
        )


def test_manager_invite_forces_developer_and_rejects_manager_role() -> None:
    repo = FakeUserRepository()
    mgr = make_user(user_id="mgr-1", email="mgr@x.com", role=UserRole.MANAGER)
    repo.save(mgr)
    mailer = FakeTransactionalEmailSender()
    use_case = InviteDeveloperByManagerUseCase(
        user_repo=repo,
        token_repo=FakePasswordCredentialTokenRepository(),
        tokens=FakeSessionTokenService(),
        mailer=mailer,
        hasher=FakePasswordHasher(),
        id_gen=FakeIdGenerator(),
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
        policy=_policy(),
    )
    result = use_case.execute(
        actor_id="mgr-1",
        cmd=InviteDeveloperCommand(name="Dev", email="d@empresa.com"),
    )
    assert result.message == messages.INVITE_DEVELOPER_SUCCESS
    assert not hasattr(result, "initial_password") or "initial_password" not in result.model_dump()
    created = repo.get_by_email("d@empresa.com")
    assert created is not None
    assert created.role == UserRole.DEVELOPER
    assert created.is_active is False
    assert created.invitation_status == "pending"
    assert created.invited_by_user_id == "mgr-1"
    assert mailer.sent
    assert "dev_cambiar_contrasena" not in mailer.sent[0][1]

    with pytest.raises(AccessDeniedError):
        use_case.execute(
            actor_id="mgr-1",
            cmd=InviteDeveloperCommand(name="Bad", email="b@empresa.com", role="manager"),
        )


def test_list_users_filters_by_name_and_role() -> None:
    repo = FakeUserRepository()
    admin = make_user(user_id="a1", email="admin@x.com", role=UserRole.ADMIN, name="Admin")
    repo.save(admin)
    repo.save(make_user(user_id="m1", email="m@x.com", role=UserRole.MANAGER, name="Ana Manager"))
    repo.save(
        make_user(user_id="d1", email="d@x.com", role=UserRole.DEVELOPER, name="Ana Developer")
    )
    use_case = ListAdminUsersUseCase(repo)
    all_users = use_case.execute(actor_id="a1")
    assert len(all_users) == 3
    filtered = use_case.execute(actor_id="a1", name="Ana", role="developer")
    assert len(filtered) == 1
    assert filtered[0].email == "d@x.com"


def test_update_user_blocks_manager_with_projects() -> None:
    repo = FakeUserRepository()
    admin = make_user(user_id="admin-1", email="admin@x.com", role=UserRole.ADMIN)
    mgr = make_user(user_id="mgr-1", email="mgr@x.com", role=UserRole.MANAGER, name="Lead")
    repo.save(admin)
    repo.save(mgr)
    ownership = FakeProjectOwnershipQuery(owns=True)
    use_case = UpdateUserByAdminUseCase(
        user_repo=repo,
        project_ownership=ownership,
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
    )
    with pytest.raises(ManagerRoleChangeBlockedError):
        use_case.execute(
            actor_id="admin-1",
            user_id="mgr-1",
            cmd=UpdateUserByAdminCommand(name="Lead", email="mgr@x.com", role="developer"),
        )


def test_update_user_duplicate_email() -> None:
    repo = FakeUserRepository()
    admin = make_user(user_id="admin-1", email="admin@x.com", role=UserRole.ADMIN)
    repo.save(admin)
    repo.save(make_user(user_id="u1", email="one@x.com", role=UserRole.DEVELOPER))
    repo.save(make_user(user_id="u2", email="two@x.com", role=UserRole.DEVELOPER))
    use_case = UpdateUserByAdminUseCase(
        user_repo=repo,
        project_ownership=FakeProjectOwnershipQuery(),
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
    )
    with pytest.raises(EmailAlreadyRegisteredError):
        use_case.execute(
            actor_id="admin-1",
            user_id="u1",
            cmd=UpdateUserByAdminCommand(name="One", email="two@x.com", role="developer"),
        )
