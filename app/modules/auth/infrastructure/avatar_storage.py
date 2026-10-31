"""Local avatar file storage (HU_DN_01_21)."""

from pathlib import Path

from app.config import settings
from app.modules.auth.domain.errors import AvatarValidationError


def _detect_image_ext(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8"):
        return "jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


class LocalAvatarStorage:
    def __init__(self, base_dir: str | None = None) -> None:
        self._base = Path(base_dir or settings.AVATAR_STORAGE_DIR)

    def save(self, *, user_id: str, content: bytes) -> str:
        if len(content) > settings.AVATAR_MAX_BYTES:
            raise AvatarValidationError()
        ext = _detect_image_ext(content)
        if ext is None:
            raise AvatarValidationError()
        self._base.mkdir(parents=True, exist_ok=True)
        key = f"{user_id}.{ext}"
        path = self._base / key
        path.write_bytes(content)
        return key

    def read(self, key: str) -> tuple[bytes, str]:
        path = self._base / key
        if not path.is_file():
            raise FileNotFoundError(key)
        ext = path.suffix.lower().lstrip(".")
        media = "image/jpeg" if ext == "jpg" else f"image/{ext}"
        return path.read_bytes(), media
