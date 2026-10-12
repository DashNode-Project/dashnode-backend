"""
Composition root for Auth module use cases.
@sad AD-09, HC-08
@origin [SAD-Propuesto]
"""

from datetime import timedelta

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth.application.dtos import SecurityPolicy
from app.modules.auth.application.password_reset_use_cases import (
    AdminRequestPasswordResetUseCase,
    CompletePasswordResetUseCase,
    CredentialTokenPolicy,
    RequestPasswordResetUseCase,
)
from app.modules.auth.application.session_use_cases import (
    AuthenticateSessionUseCase,
    LoginUseCase,
    LogoutUseCase,
)
from app.modules.auth.application.use_cases import RegisterManagerUseCase
from app.modules.auth.application.user_administration_use_cases import (
    CreateUserByAdminUseCase,
    InviteDeveloperByManagerUseCase,
    ListAdminUsersUseCase,
)
from app.modules.auth.infrastructure.email_sender import (
    LoggingTransactionalEmailSender,
    SmtpTransactionalEmailSender,
)
from app.modules.auth.infrastructure.repositories import (
    SqlAlchemyLoginAttemptRepository,
    SqlAlchemyPasswordCredentialTokenRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from app.modules.auth.infrastructure.session_tokens import SecureSessionTokenService
from app.orchestration.security import SessionAuthenticator
from app.shared.application.identity import CurrentSession, CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork
from app.shared.infrastructure.database import get_db_session as get_db
from app.shared.infrastructure.hasher import Argon2PasswordHasher
from app.shared.infrastructure.id_generator import UuidGenerator

clock = SystemClock()
id_generator = UuidGenerator()
password_hasher = Argon2PasswordHasher()
session_tokens = SecureSessionTokenService()


def security_policy() -> SecurityPolicy:
    return SecurityPolicy(
        session_ttl=timedelta(hours=settings.SESSION_TTL_HOURS),
        session_retention=timedelta(hours=settings.SESSION_COOKIE_RETENTION_HOURS),
        max_failed_attempts=settings.LOGIN_MAX_FAILED_ATTEMPTS,
        attempt_window=timedelta(minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES),
    )

def security_policy() -> SecurityPolicy:
    return SecurityPolicy(
        session_ttl=timedelta(hours=settings.SESSION_TTL_HOURS),
        session_retention=timedelta(hours=settings.SESSION_COOKIE_RETENTION_HOURS),
        max_failed_attempts=settings.LOGIN_MAX_FAILED_ATTEMPTS,
        attempt_window=timedelta(minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES),
    )

def get_register_manager_use_case(
    db: Session = Depends(get_db),
) -> RegisterManagerUseCase:
    return RegisterManagerUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        hasher=password_hasher,
        id_gen=id_generator,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def get_login_use_case(
    db: Session = Depends(get_db),
) -> LoginUseCase:
    return LoginUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        session_repo=SqlAlchemySessionRepository(session=db),
        attempt_repo=SqlAlchemyLoginAttemptRepository(session=db),
        hasher=password_hasher,
        tokens=session_tokens,
        id_gen=id_generator,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
        policy=security_policy(),
    )


def credential_token_policy() -> CredentialTokenPolicy:
    return CredentialTokenPolicy(
        reset_ttl=timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        activation_ttl=timedelta(hours=settings.PASSWORD_ACTIVATION_TTL_HOURS),
        frontend_base_url=settings.FRONTEND_BASE_URL,
    )


def get_transactional_email_sender() -> (
    LoggingTransactionalEmailSender | SmtpTransactionalEmailSender
):
    if settings.SMTP_HOST:
        return SmtpTransactionalEmailSender()
    return LoggingTransactionalEmailSender()


def get_request_password_reset_use_case(
    db: Session = Depends(get_db),
) -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        token_repo=SqlAlchemyPasswordCredentialTokenRepository(session=db),
        tokens=session_tokens,
        mailer=get_transactional_email_sender(),
        id_gen=id_generator,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
        policy=credential_token_policy(),
    )


def get_complete_password_reset_use_case(
    db: Session = Depends(get_db),
) -> CompletePasswordResetUseCase:
    return CompletePasswordResetUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        token_repo=SqlAlchemyPasswordCredentialTokenRepository(session=db),
        tokens=session_tokens,
        hasher=password_hasher,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def get_admin_request_password_reset_use_case(
    db: Session = Depends(get_db),
) -> AdminRequestPasswordResetUseCase:
    return AdminRequestPasswordResetUseCase(
        actor_repo=SqlAlchemyUserRepository(session=db),
        user_repo=SqlAlchemyUserRepository(session=db),
        token_repo=SqlAlchemyPasswordCredentialTokenRepository(session=db),
        tokens=session_tokens,
        mailer=get_transactional_email_sender(),
        id_gen=id_generator,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
        policy=credential_token_policy(),
    )


def get_list_admin_users_use_case(db: Session = Depends(get_db)) -> ListAdminUsersUseCase:
    return ListAdminUsersUseCase(user_repo=SqlAlchemyUserRepository(session=db))


def get_create_user_by_admin_use_case(
    db: Session = Depends(get_db),
) -> CreateUserByAdminUseCase:
    return CreateUserByAdminUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        token_repo=SqlAlchemyPasswordCredentialTokenRepository(session=db),
        tokens=session_tokens,
        mailer=get_transactional_email_sender(),
        hasher=password_hasher,
        id_gen=id_generator,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
        policy=credential_token_policy(),
    )


def get_invite_developer_use_case(db: Session = Depends(get_db)) -> InviteDeveloperByManagerUseCase:
    return InviteDeveloperByManagerUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        token_repo=SqlAlchemyPasswordCredentialTokenRepository(session=db),
        tokens=session_tokens,
        mailer=get_transactional_email_sender(),
        hasher=password_hasher,
        id_gen=id_generator,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
        policy=credential_token_policy(),
    )


def get_logout_use_case(
    db: Session = Depends(get_db),
) -> LogoutUseCase:
    return LogoutUseCase(
        session_repo=SqlAlchemySessionRepository(session=db),
        tokens=session_tokens,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def build_session_authenticator(db: Session) -> SessionAuthenticator:
    """Factory registered in `app.main`; keeps other modules unaware of auth internals."""
    use_case = AuthenticateSessionUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        session_repo=SqlAlchemySessionRepository(session=db),
        tokens=session_tokens,
        clock=clock,
    )

    def authenticate(token: str | None) -> CurrentSession:
        info = use_case.execute(token)
        user = info.user
        return CurrentSession(
            user=CurrentUser(
                id=user.id,
                email=user.email,
                name=user.name,
                role=user.role.value,
                is_active=user.is_active,
                created_at=user.created_at,
            ),
            expires_at=info.expires_at,
        )

    return authenticate
