"""
API tests for Auth routes.
@sad 4.1.1
"""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.shared.infrastructure.database import Base, get_db_session

# In-memory SQLite for testing API end-to-end
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    db: Session = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db_session] = override_get_db
client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_and_login_flow() -> None:
    # 1. Register
    reg_payload = {
        "email": "testuser@dashnode.io",
        "password": "Password1234!",
        "name": "Integration User",
        "role": "developer",
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == "testuser@dashnode.io"
    assert user_data["name"] == "Integration User"
    assert "id" in user_data

    # 2. Login
    login_payload = {
        "email": "testuser@dashnode.io",
        "password": "Password1234!",
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 3. Get /me with Bearer token
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "testuser@dashnode.io"
    assert me_data["id"] == user_data["id"]


def test_login_invalid_credentials() -> None:
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@dashnode.io", "password": "wrongpassword123"},
    )
    assert login_resp.status_code == 401


def test_me_without_token() -> None:
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401
