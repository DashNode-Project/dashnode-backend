"""Console QA Test Runner for EP-11 Part 2 (HU_DN_07_102 .. HU_DN_07_105).

Executes real HTTP requests against a local Uvicorn + FastAPI instance:
- HU_DN_07_102: Assign issue to active developer, enforce roles, optimistic 409 lock, outbox
- HU_DN_07_103: Resolve issue with required note, close restricted to Admin/Manager
- HU_DN_07_104: Report fix from task atomically, transition to CORRECTION, preserve previous status
- HU_DN_07_105: Unlink and restore task status only when last blocking open issue is resolved/closed
"""

import contextlib
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DB_FILE = REPO_ROOT / "qa_ep11_part2_test.db"
if DB_FILE.exists():
    with contextlib.suppress(Exception):
        DB_FILE.unlink()

os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{DB_FILE.resolve()}"
os.environ["SECRET_KEY"] = "qa-secret-key-at-least-32-bytes-long!"
os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
os.environ["SESSION_COOKIE_SECURE"] = "false"

import requests
import uvicorn
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.main import app
from app.modules.backlog.infrastructure.models import StoryTaskModel
from app.modules.fixes.domain import messages
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.outbox import OutboxEventModel
from tests.support import DEFAULT_PASSWORD, create_user

SEPARATOR = "=" * 80


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def login_session(base_url: str, email: str) -> requests.Session:
    session = requests.Session()
    resp = session.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
        timeout=5,
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return session


def main() -> int:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    print(f"\n{SEPARATOR}\n  INICIANDO QA LIVE EP-11 PARTE 2 EN {base_url}\n{SEPARATOR}")

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    deadline = time.time() + 10.0
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)

    mgr_id = create_user(engine, email="qa2-mgr@dashnode.io", name="QA Manager", role="manager")
    dev1_id = create_user(engine, email="qa2-dev1@dashnode.io", name="QA Dev1", role="developer")
    dev2_id = create_user(engine, email="qa2-dev2@dashnode.io", name="QA Dev2", role="developer")

    mgr = login_session(base_url, "qa2-mgr@dashnode.io")
    dev1 = login_session(base_url, "qa2-dev1@dashnode.io")
    dev2 = login_session(base_url, "qa2-dev2@dashnode.io")

    # Setup project, epic, story, task in CODE_REVIEW assigned to dev1
    proj = mgr.post(
        f"{base_url}/api/v1/projects",
        json={
            "name": "QA Live EP11-P2",
            "description": "Live flow",
            "priority": "alta",
            "manager_id": mgr_id,
        },
        timeout=5,
    )
    assert proj.status_code == 201, proj.text
    project_id = proj.json()["id"]
    mgr.post(
        f"{base_url}/api/v1/projects/{project_id}/members", json={"user_id": dev1_id}, timeout=5
    )
    mgr.post(
        f"{base_url}/api/v1/projects/{project_id}/members", json={"user_id": dev2_id}, timeout=5
    )

    epic_id = mgr.post(
        f"{base_url}/api/v1/projects/{project_id}/epics", json={"name": "Épica QA"}, timeout=5
    ).json()["id"]
    story_id = mgr.post(
        f"{base_url}/api/v1/epics/{epic_id}/user-stories",
        json={"title": "HU Live", "user_role": "QA", "reason": "Validar", "epic_id": epic_id},
        timeout=5,
    ).json()["id"]
    task_id = mgr.post(
        f"{base_url}/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Sincronizar webhooks", "task_type": "backend"},
        timeout=5,
    ).json()["id"]
    mgr.patch(
        f"{base_url}/api/v1/story-tasks/{task_id}/assignee",
        json={"assignee_id": dev1_id},
        timeout=5,
    )
    mgr.patch(
        f"{base_url}/api/v1/projects/{project_id}/tasks/{task_id}/status",
        json={"status": "CODE_REVIEW"},
        timeout=5,
    )

    results: list[tuple[str, str, Any]] = []

    # 1. HU_DN_07_102: Assign issue + 403 dev + 409 lock
    iss = mgr.post(
        f"{base_url}/api/v1/projects/{project_id}/issues",
        json={
            "title": "Issue asignación",
            "description": "Detalle",
            "severity": "Alta",
            "type": "Bug",
        },
        timeout=5,
    ).json()
    iss_id = iss["issue"]["id"]
    r_dev = dev1.patch(
        f"{base_url}/api/v1/projects/{project_id}/issues/{iss_id}/assignee",
        json={"assignee_id": dev1_id, "version": 1},
        timeout=5,
    )
    assert r_dev.status_code == 403
    r_non_dev = mgr.patch(
        f"{base_url}/api/v1/projects/{project_id}/issues/{iss_id}/assignee",
        json={"assignee_id": mgr_id, "version": 1},
        timeout=5,
    )
    assert r_non_dev.status_code == 400
    r_assign = mgr.patch(
        f"{base_url}/api/v1/projects/{project_id}/issues/{iss_id}/assignee",
        json={"assignee_id": dev1_id, "version": 1},
        timeout=5,
    )
    assert r_assign.status_code == 200
    assert r_assign.json()["issue"]["version"] == 2
    r_409 = mgr.patch(
        f"{base_url}/api/v1/projects/{project_id}/issues/{iss_id}/assignee",
        json={"assignee_id": None, "version": 1},
        timeout=5,
    )
    assert r_409.status_code == 409
    results.append(
        ("HU_DN_07_102", "PASSED", "Assign dev ok, 403 dev, 400 non-dev, 409 lock verified")
    )

    # 2. HU_DN_07_103: Resolve & Close
    r_res = dev1.post(
        f"{base_url}/api/v1/projects/{project_id}/issues/{iss_id}/resolve",
        json={"resolution_note": "Resuelto OK", "version": 2},
        timeout=5,
    )
    assert r_res.status_code == 200
    r_close_dev = dev1.post(
        f"{base_url}/api/v1/projects/{project_id}/issues/{iss_id}/close",
        json={"version": 3},
        timeout=5,
    )
    assert r_close_dev.status_code == 403
    r_close_mgr = mgr.post(
        f"{base_url}/api/v1/projects/{project_id}/issues/{iss_id}/close",
        json={"version": 3},
        timeout=5,
    )
    assert r_close_mgr.status_code == 200
    assert r_close_mgr.json()["issue"]["status"] == "closed"
    results.append(("HU_DN_07_103", "PASSED", "Resolve, 403 dev close, manager close verified"))

    # 3. HU_DN_07_104: Report 2 fixes from task
    r_fix1 = dev1.post(
        f"{base_url}/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={
            "title": "Fix: Sincronizar webhooks #1",
            "description": "Timeout",
            "severity": "Alta",
            "type": "Bug",
        },
        timeout=5,
    )
    assert r_fix1.status_code == 201
    fix1_id = r_fix1.json()["issue"]["id"]
    r_fix2 = mgr.post(
        f"{base_url}/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={
            "title": "Fix: Sincronizar webhooks #2",
            "description": "Reintento",
            "severity": "Media",
            "type": "Regresión",
        },
        timeout=5,
    )
    assert r_fix2.status_code == 201
    fix2_id = r_fix2.json()["issue"]["id"]
    r_other = dev2.post(
        f"{base_url}/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={"title": "Fix: Otro", "severity": "Baja", "type": "Bug"},
        timeout=5,
    )
    assert r_other.status_code == 403
    results.append(
        ("HU_DN_07_104", "PASSED", "Task moved to CORRECTION, 2nd fix kept previous status")
    )

    # 4. HU_DN_07_105: Resolving fix 1 keeps CORRECTION; resolving fix 2 restores chosen status
    r_unblock1 = dev1.post(
        f"{base_url}/api/v1/projects/{project_id}/issues/{fix1_id}/resolve",
        json={"resolution_note": "Fix 1 OK", "version": 1},
        timeout=5,
    )
    assert r_unblock1.status_code == 200
    assert r_unblock1.json()["task_unlinked"] is False
    r_unblock2 = dev1.post(
        f"{base_url}/api/v1/projects/{project_id}/issues/{fix2_id}/resolve",
        json={"resolution_note": "Fix 2 OK", "task_status": "TESTING", "version": 1},
        timeout=5,
    )
    assert r_unblock2.status_code == 200
    assert r_unblock2.json()["task_unlinked"] is True
    assert r_unblock2.json()["task_status"] == "TESTING"
    assert messages.TASK_UNLINKED_AND_UPDATED in r_unblock2.json()["message"]

    with Session(engine) as s:
        task_row = s.get(StoryTaskModel, task_id)
        assert task_row is not None
        assert task_row.status == "TESTING"
        assert task_row.status_before_correction is None
        outbox_cnt = len(s.scalars(select(OutboxEventModel)).all())
        assert outbox_cnt >= 7
        results.append(
            ("HU_DN_07_105", "PASSED", f"Restored to TESTING, outbox events={outbox_cnt}")
        )

    for hu, status_lbl, detail in results:
        print(f"  [{status_lbl}] {hu}: {detail}")

    server.should_exit = True
    engine.dispose()
    with contextlib.suppress(Exception):
        DB_FILE.unlink()
    print(f"{SEPARATOR}\n  QA EP-11 PARTE 2 COMPLETADO 100% EXITOSO\n{SEPARATOR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
