"""Validation rules for Projects (EP-03 backlog literals)."""

from urllib.parse import urlparse

from app.modules.projects.domain import messages
from app.modules.projects.domain.entities import ProjectPriority, ProjectStatus


def validate_project_name(name: str) -> dict[str, str]:
    if not name.strip():
        return {"name": messages.PROJECT_NAME_REQUIRED}
    if len(name.strip()) > 100:
        return {"name": "El nombre del proyecto no puede exceder 100 caracteres."}
    return {}


def validate_meeting_link(link: str | None) -> dict[str, str]:
    if link is None or not link.strip():
        return {}
    parsed = urlparse(link.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {"meeting_link": messages.MEETING_LINK_INVALID}
    return {}


def validate_manager_id(manager_id: str | None) -> dict[str, str]:
    if not manager_id or not str(manager_id).strip():
        return {"manager_id": messages.MANAGER_REQUIRED}
    return {}


def parse_priority(value: str) -> ProjectPriority | None:
    try:
        return ProjectPriority(value)
    except ValueError:
        return None


def parse_status(value: str) -> ProjectStatus | None:
    try:
        return ProjectStatus(value)
    except ValueError:
        return None
