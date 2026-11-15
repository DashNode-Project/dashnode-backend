"""Administrators are scoped to user administration, not operational modules."""

from app.shared.application.identity import CurrentUser
from app.shared.domain.authorization import AccessDeniedError


def deny_admin_operational_access(actor: CurrentUser) -> None:
    if actor.role == "admin":
        raise AccessDeniedError()
