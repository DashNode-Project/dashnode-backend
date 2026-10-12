"""
Helpers for API tests: create users directly in the database and authenticate them.
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.modules.auth.infrastructure.models import UserModel
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.hasher import Argon2PasswordHasher
from app.shared.infrastructure.id_generator import UuidGenerator

DEFAULT_PASSWORD = "Password1234"


def create_user(
    engine: Engine,
    *,
    email: str,
    role: str = "developer",
    password: str = DEFAULT_PASSWORD,
    name: str = "Test User",
    is_active: bool = True,
) -> str:
    """Insert a user bypassing the public API (which only registers Managers)."""
    now = SystemClock().now()
    user_id = UuidGenerator().generate()
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        session.add(
            UserModel(
                id=user_id,
                email=email,
                hashed_password=Argon2PasswordHasher().hash(password),
                name=name,
                role=role,
                is_active=is_active,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()
    return user_id


def legacy_auth_headers(
    client: TestClient, engine: Engine, *, email: str, role: str = "developer"
) -> dict[str, str]:
    """Create a user and obtain a Bearer token (legacy flow, replaced in HU_DN_01_03)."""
    create_user(engine, email=email, role=role)
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
