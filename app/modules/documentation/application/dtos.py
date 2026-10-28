"""DTOs for Documentation application layer (EP-09)."""

import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel

from app.modules.documentation.domain import messages

_URL_REGEX = re.compile(
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


def is_valid_url(val: str | None) -> bool:
    if val is None or not val.strip():
        return True
    cleaned = val.strip()
    try:
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
    except Exception:
        return False
    return bool(_URL_REGEX.match(cleaned))


def validate_optional_url(val: str | None) -> str | None:
    if val is None or not val.strip():
        return None
    cleaned = val.strip()
    if not is_valid_url(cleaned):
        raise ValueError(messages.INVALID_URL)
    return cleaned


class CreateDocumentationCommand(BaseModel):
    title: str = ""
    category: str = ""
    objective: str | None = None
    tags: str | None = None
    content: str | None = None
    external_url: str | None = None
    is_pinned: bool = False


class UpdateDocumentationCommand(BaseModel):
    title: str = ""
    category: str = ""
    objective: str | None = None
    tags: str | None = None
    content: str | None = None
    external_url: str | None = None
    approval_status: str | None = None
    is_pinned: bool | None = None


class DocumentationEntryDTO(BaseModel):
    id: str
    project_id: str
    author_id: str
    author_name: str | None = None
    title: str
    category: str
    objective: str | None = None
    tags: str | None = None
    content: str | None = None
    external_url: str | None = None
    approval_status: str
    is_pinned: bool
    is_visible_to_devs: bool = True
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    can_edit: bool = False
    can_delete: bool = False
    can_approve: bool = False


class UpdateVisibilityCommand(BaseModel):
    is_visible_to_devs: bool


class RejectDocumentationCommand(BaseModel):
    rejection_reason: str | None = None


class ResubmitDocumentationCommand(BaseModel):
    title: str = ""
    category: str = ""
    objective: str | None = None
    tags: str | None = None
    content: str | None = None
    external_url: str | None = None


class DocumentationListResponse(BaseModel):
    entries: list[DocumentationEntryDTO]
    message: str | None = None


class DocumentationOperationResponse(BaseModel):
    message: str
    entry: DocumentationEntryDTO | None = None
