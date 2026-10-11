"""
Unit tests for Auth domain entities.
@sad 4.1.1, AD-08
"""

from datetime import UTC, datetime

from app.modules.auth.domain.entities import User, UserRole


def test_user_can_authenticate_when_active() -> None:
    now = datetime.now(UTC)
    user = User(
        id="usr-1",
        email="test@example.com",
        hashed_password="hash",
        name="Test User",
        role=UserRole.DEVELOPER,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    assert user.can_authenticate() is True


def test_user_cannot_authenticate_when_inactive() -> None:
    now = datetime.now(UTC)
    user = User(
        id="usr-1",
        email="test@example.com",
        hashed_password="hash",
        name="Test User",
        role=UserRole.DEVELOPER,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.deactivate(now)
    assert user.is_active is False
    assert user.can_authenticate() is False
