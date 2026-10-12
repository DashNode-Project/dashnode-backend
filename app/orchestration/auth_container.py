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
from app.modules.auth.application.session_use_cases import (
    AuthenticateSessionUseCase,
    LoginUseCase,
)
from app.modules.auth.application.use_cases import RegisterManagerUseCase
from app.modules.auth.infrastructure.repositories import (
    SqlAlchemyLoginAttemptRepository,
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
