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


class LoginValidationError(AppError):
    """Login payload is blank or the e-mail has an invalid format."""

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


class InvalidCredentialsError(AppError):
    """Unknown e-mail or wrong password: deliberately indistinguishable."""

    def __init__(self) -> None:
        super().__init__(
            "INVALID_CREDENTIALS", messages.INVALID_CREDENTIALS, ErrorKind.UNAUTHENTICATED
        )


class LoginAttemptsExceededError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "LOGIN_ATTEMPTS_EXCEEDED", messages.LOGIN_ATTEMPTS_EXCEEDED, ErrorKind.RATE_LIMITED
        )


class AccountDisabledError(AppError):
    def __init__(self) -> None:
        super().__init__("ACCOUNT_DISABLED", messages.ACCOUNT_DISABLED, ErrorKind.FORBIDDEN)


class SessionExpiredError(AppError):
    def __init__(self) -> None:
        super().__init__("SESSION_EXPIRED", messages.SESSION_EXPIRED, ErrorKind.UNAUTHENTICATED)


class NotAuthenticatedError(AppError):
    def __init__(self) -> None:
        super().__init__("NOT_AUTHENTICATED", messages.NOT_AUTHENTICATED, ErrorKind.UNAUTHENTICATED)


class PasswordResetValidationError(AppError):
    def __init__(self, code: str, message: str, fields: dict[str, str]) -> None:
        super().__init__(code, message, ErrorKind.VALIDATION, fields)


class EmailSendFailedError(AppError):
    def __init__(self) -> None:
        super().__init__("EMAIL_SEND_FAILED", messages.EMAIL_SEND_FAILED, ErrorKind.VALIDATION)


class InvalidCredentialTokenError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "INVALID_OR_EXPIRED_LINK", messages.INVALID_OR_EXPIRED_LINK, ErrorKind.VALIDATION
        )


class AdminResetDisabledTargetError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "ADMIN_RESET_DISABLED_TARGET",
            messages.ADMIN_RESET_DISABLED_TARGET,
            ErrorKind.VALIDATION,
        )


class UserAdministrationValidationError(AppError):
    def __init__(self, code: str, message: str, fields: dict[str, str]) -> None:
        super().__init__(code, message, ErrorKind.VALIDATION, fields)


class ManagerRoleChangeBlockedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "MANAGER_ROLE_CHANGE_BLOCKED",
            messages.MANAGER_ROLE_CHANGE_BLOCKED,
            ErrorKind.VALIDATION,
        )


class SelfDeactivateBlockedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "SELF_DEACTIVATE_BLOCKED",
            messages.SELF_DEACTIVATE_BLOCKED,
            ErrorKind.VALIDATION,
        )


class ManagerDeactivateBlockedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "MANAGER_DEACTIVATE_BLOCKED",
            messages.MANAGER_DEACTIVATE_BLOCKED,
            ErrorKind.VALIDATION,
        )


class ReactivateNotInactiveError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "REACTIVATE_NOT_INACTIVE",
            messages.REACTIVATE_NOT_INACTIVE,
            ErrorKind.VALIDATION,
        )


class ProfileValidationError(AppError):
    def __init__(self, code: str, message: str, fields: dict[str, str]) -> None:
        super().__init__(code, message, ErrorKind.VALIDATION, fields)


class AvatarValidationError(AppError):
    def __init__(self) -> None:
        super().__init__("AVATAR_INVALID", messages.AVATAR_INVALID, ErrorKind.VALIDATION)
