"""
API tests for Projects routes.
@sad 4.1.2
"""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.shared.infrastructure.database import Base, get_db_session

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


def test_projects_crud_flow() -> None:
    # 1. Register and login a user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "pm@dashnode.io",
            "password": "Password1234!",
            "name": "Project Manager",
            "role": "manager",
        },
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "pm@dashnode.io", "password": "Password1234!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create project
    create_resp = client.post(
        "/api/v1/projects",
        json={"name": "Alpha Project", "description": "First project"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    proj_data = create_resp.json()
    assert proj_data["name"] == "Alpha Project"
    proj_id = proj_data["id"]

    # 3. List projects
    list_resp = client.get("/api/v1/projects", headers=headers)
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) >= 1
    assert any(p["id"] == proj_id for p in projects)

    # 4. Get single project
    get_resp = client.get(f"/api/v1/projects/{proj_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == proj_id

    # 5. Add a member
    add_resp = client.post(
        f"/api/v1/projects/{proj_id}/members",
        json={"user_id": "dev-user-id", "role": "member"},
        headers=headers,
    )
    assert add_resp.status_code == 201
    member_data = add_resp.json()
    assert member_data["project_id"] == proj_id
    assert member_data["user_id"] == "dev-user-id"
