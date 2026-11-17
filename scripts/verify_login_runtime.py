"""Smoke test: DB ready + manager login against running API or in-process TestClient."""

from __future__ import annotations

import sys
from pathlib import Path

backend = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend))

from fastapi.testclient import TestClient

from app.main import app
from app.shared.infrastructure.database import initialize_database


def main() -> int:
    status = initialize_database()
    print(f"database: {status.role.value} ({status.url_label})")

    client = TestClient(app)
    ready = client.get("/health/ready")
    print("health/ready", ready.status_code, ready.json())
    if ready.status_code != 200:
        return 1

    from app.config import settings

    email = settings.SEED_MANAGER_EMAIL or "manager@dashnode.local"
    password = (
        settings.SEED_MANAGER_PASSWORD.get_secret_value() if settings.SEED_MANAGER_PASSWORD else ""
    )
    if not password:
        print("[skip] login: SEED_MANAGER_PASSWORD not set")
        return 0

    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    print("login", res.status_code, res.json().get("message", res.text)[:120])
    return 0 if res.status_code == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())