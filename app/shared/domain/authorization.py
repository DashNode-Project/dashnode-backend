"""Cross-cutting authorization errors (HU_DN_01_09)."""

from app.shared.domain.errors import AppError, ErrorKind
from app.shared.domain.messages import ACCESS_DENIED


class AccessDeniedError(AppError):
    def __init__(self) -> None:
        super().__init__("ACCESS_DENIED", ACCESS_DENIED, ErrorKind.FORBIDDEN)
