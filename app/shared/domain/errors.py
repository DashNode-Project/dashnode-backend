"""
Transport-agnostic application errors.

Every error carries a stable machine-readable `code` and the user-facing `message`
defined by the user story. The API layer maps `kind` to an HTTP status.
@sad AD-08
@origin [Archetype Convention Addition]
"""

from enum import StrEnum


class ErrorKind(StrEnum):
    VALIDATION = "validation"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"


class AppError(Exception):
    """Expected business or security error with a literal, user-facing message."""

    def __init__(
        self,
        code: str,
        message: str,
        kind: ErrorKind,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind
        self.fields: dict[str, str] = fields or {}
