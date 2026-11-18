"""Quick smoke audit against a running API (manager session cookie)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings

BASE = "http://127.0.0.1:8000/api/v1"


def login(client: httpx.Client, email: str, password: str) -> None:
    r = client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else (settings.SEED_MANAGER_EMAIL or "")
    password = (
        sys.argv[2]
        if len(sys.argv) > 2
        else (
            settings.SEED_MANAGER_PASSWORD.get_secret_value()
            if settings.SEED_MANAGER_PASSWORD
            else ""
        )
    )
    if not email or not password:
        print("[fail] set SEED_MANAGER_EMAIL/PASSWORD or pass argv")
        sys.exit(1)
    with httpx.Client(timeout=120.0) as client:
        login(client, email, password)
        projects = client.get(f"{BASE}/projects").json()
        orbit = next((p for p in projects if "Orbit" in p.get("name", "")), None)
        if not orbit:
            print("[fail] OrbitLogistics project not found")
            sys.exit(1)
        pid = orbit["id"]
        checks: list[tuple[str, str, int]] = []
        for path in (
            f"/projects/{pid}",
            f"/projects/{pid}/health",
            f"/projects/{pid}/members",
            f"/users/me/tasks",
            f"/knowledge/system",
            f"/ai/metrics/summary?period=7d&project_id={pid}",
        ):
            r = client.get(f"{BASE}{path}")
            checks.append((path, "ok" if r.status_code == 200 else r.text[:120], r.status_code))
        kb = client.get(f"{BASE}/knowledge/system").json()
        items = kb.get("items") or []
        health = client.get(f"{BASE}/projects/{pid}/health").json()
        print(json.dumps({"orbit_id": pid, "health": health, "kb_count": len(items), "checks": checks}, indent=2))
        bad = [c for c in checks if c[2] != 200]
        if bad:
            sys.exit(2)


if __name__ == "__main__":
    main()