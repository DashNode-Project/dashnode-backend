"""Role filter helper for command catalog."""

import pytest

from app.orchestration.command_catalog import SYSTEM_COMMANDS
from app.orchestration.command_routes import _allowed


@pytest.mark.parametrize(
    ("command_id", "role", "expected"),
    [
        ("CMD-NAV-USERS", "admin", True),
        ("CMD-NAV-USERS", "developer", False),
        ("CMD-ACT-NEWPRJ", "manager", True),
        ("CMD-ACT-NEWPRJ", "developer", False),
        ("CMD-NAV-HOME", "developer", True),
    ],
)
def test_allowed_matrix(command_id: str, role: str, expected: bool) -> None:
    template = next(cmd for cmd in SYSTEM_COMMANDS if cmd.id == command_id)
    assert _allowed(template, role) is expected