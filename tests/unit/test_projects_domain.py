"""
Unit tests for Projects domain rules (EP-03).
@sad AD-08, 4.1.2
"""

from app.modules.projects.domain import messages
from app.modules.projects.domain.rules import (
    validate_manager_id,
    validate_meeting_link,
    validate_project_name,
)


def test_validate_project_name_required() -> None:
    assert validate_project_name("") == {"name": messages.PROJECT_NAME_REQUIRED}
    assert validate_project_name("  ") == {"name": messages.PROJECT_NAME_REQUIRED}


def test_validate_meeting_link() -> None:
    assert validate_meeting_link(None) == {}
    assert validate_meeting_link("https://meet.example.com/abc") == {}
    assert validate_meeting_link("not-a-url") == {"meeting_link": messages.MEETING_LINK_INVALID}


def test_validate_manager_id() -> None:
    assert validate_manager_id("") == {"manager_id": messages.MANAGER_REQUIRED}
    assert validate_manager_id("mgr-1") == {}
