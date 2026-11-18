"""Apply Alembic migrations to the active database (startup hook)."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger("dashnode.migrations")


def upgrade_head() -> None:
    backend_root = Path(__file__).resolve().parents[3]
    ini_path = backend_root / "alembic.ini"
    if not ini_path.is_file():
        logger.warning("alembic.ini not found at %s; skipping migrations", ini_path)
        return
    from app.shared.infrastructure.database_provider import select_database_url

    url, status = select_database_url()
    if status.url_label == "sqlite":
        logger.info("Skipping Alembic on sqlite fallback")
        return
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", url)
    logger.info("Alembic target provider=%s url_label=%s", status.role.value, status.url_label)
    command.upgrade(cfg, "head")
    logger.info("Alembic upgrade head completed")
