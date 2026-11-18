"""Startup migration hook."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.shared.infrastructure import run_migrations


@patch("app.shared.infrastructure.run_migrations.command.upgrade")
@patch("app.shared.infrastructure.database_provider.select_database_url")
def test_upgrade_head_skips_sqlite(select_url: MagicMock, upgrade: MagicMock) -> None:
    select_url.return_value = ("sqlite:///x.db", MagicMock(url_label="sqlite"))
    run_migrations.upgrade_head()
    upgrade.assert_not_called()


@patch("app.shared.infrastructure.run_migrations.command.upgrade")
@patch("app.shared.infrastructure.database_provider.select_database_url")
def test_upgrade_head_runs_on_postgres(select_url: MagicMock, upgrade: MagicMock) -> None:
    status = MagicMock(url_label="supabase", role=MagicMock(value="primary"))
    select_url.return_value = ("postgresql://postgres@localhost:5432/dashnode_ci", status)
    run_migrations.upgrade_head()
    upgrade.assert_called_once()


def test_upgrade_head_missing_ini() -> None:
    with patch.object(Path, "is_file", return_value=False):
        run_migrations.upgrade_head()
