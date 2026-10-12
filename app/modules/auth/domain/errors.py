"""
Domain errors of the Auth module. Each carries a stable code and a literal message.
@sad 4.1.1
@origin [HU-Spec]
"""

from app.modules.auth.domain import messages
from app.shared.domain.errors import AppError, ErrorKind


class RegistrationValidationError(AppError):
    """One or more registration fields are missing or invalid."""

    def __init__(self, code: str, message: str, fields: dict[str, str]) -> None:
        super().__init__(code, message, ErrorKind.VALIDATION, fields)


class EmailAlreadyRegisteredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "EMAIL_ALREADY_REGISTERED",
            messages.EMAIL_ALREADY_REGISTERED,
            ErrorKind.CONFLICT,
            {"email": messages.EMAIL_ALREADY_REGISTERED},
        )


class RegistrationRoleNotAllowedError(AppError):
    def __init__(self) -> None:
        super().__init__("ROLE_NOT_ALLOWED", messages.ROLE_NOT_ALLOWED, ErrorKind.FORBIDDEN)
