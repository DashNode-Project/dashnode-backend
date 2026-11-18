"""Migrate, seed users, knowledge FAQ and FIX-01 demo projects on the active DB provider.

Usage (from backend root, .env with SUPABASE_DB_PASSWORD set for cloud):
  python scripts/db_bootstrap.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

backend = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend))

from app.config import settings
from app.shared.infrastructure.database import get_database_provider_status, initialize_database


def _run(cmd: list[str]) -> None:
    print(f"[run] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=backend, check=True)


def main() -> None:
    if settings.supabase_database_url() is None:
        print(
            "[warn] SUPABASE_DB_PASSWORD vacío: se usará DATABASE_URL local. "
            "Para datos en Supabase, complete SUPABASE_DB_PASSWORD en .env."
        )
    status = initialize_database()
    prov = get_database_provider_status() or status
    print(f"[db] provider={prov.role.value} label={prov.url_label}")
    if prov.limitations:
        print(f"[db] {prov.limitations}")

    _run([sys.executable, "-m", "alembic", "upgrade", "head"])
    _run([sys.executable, "-m", "app.cli.seed"])
    _run([sys.executable, "scripts/seed_system_knowledge_faq.py"])
    _run([sys.executable, "scripts/seed_fix01_demo_projects.py"])
    _run([sys.executable, "scripts/repair_demo_integrity.py"])
    print("[ok] Bootstrap complete.")


if __name__ == "__main__":
    main()
