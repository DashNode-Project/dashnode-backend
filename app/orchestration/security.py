"""
Security orchestration: resolves the caller identity from the session cookie.

Feature modules must not import each other (BR-4, checked transitively), so this file
knows nothing about the auth module: the concrete authenticator is injected at
start-up by `app.main` through `register_session_authenticator`.
@sad AD-09, 4.1.1
@origin [HU-Spec]
"""

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.shared.application.identity import CurrentSession, CurrentUser
from app.shared.infrastructure.database import get_db_session

SessionAuthenticator = Callable[[str | None], CurrentSession]
SessionAuthenticatorFactory = Callable[[Session], SessionAuthenticator]

_factory: SessionAuthenticatorFactory | None = None


def register_session_authenticator(factory: SessionAuthenticatorFactory) -> None:
    """Wire the concrete session validation (called once by the composition root)."""
    global _factory
    _factory = factory


def get_session_token(request: Request) -> str | None:
    """Opaque session token from the HttpOnly cookie (never from headers or the body)."""
    return request.cookies.get(settings.SESSION_COOKIE_NAME)


def get_current_session(
    token: str | None = Depends(get_session_token),
    db: Session = Depends(get_db_session),
) -> CurrentSession:
    """Validate the session on the server; raises the story's literal errors."""
    if _factory is None:
        raise RuntimeError("Session authenticator has not been registered.")
    return _factory(db)(token)


def get_current_user(session: CurrentSession = Depends(get_current_session)) -> CurrentUser:
    """FastAPI dependency used by every protected endpoint."""
    return session.user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    from app.shared.domain.authorization import AccessDeniedError

    if user.role != "admin":
        raise AccessDeniedError()
    return user


def require_manager(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    from app.shared.domain.authorization import AccessDeniedError

    if user.role != "manager":
        raise AccessDeniedError()
    return user


def require_admin_or_manager(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    from app.shared.domain.authorization import AccessDeniedError

    if user.role not in ("admin", "manager"):
        raise AccessDeniedError()
    return user


def require_non_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Managers and developers only; administrators manage users (EP-01)."""
    from app.shared.domain.authorization import AccessDeniedError

    if user.role == "admin":
        raise AccessDeniedError()
    return user
