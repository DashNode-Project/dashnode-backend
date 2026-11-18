"""Command catalog helpers (EP-15)."""

from app.orchestration.command_catalog import CATALOG_VERSION, SYSTEM_COMMANDS, home_segment


def test_home_segment_per_role() -> None:
    assert home_segment("admin") == "administrador"
    assert home_segment("manager") == "gerente"
    assert home_segment("developer") == "desarrollador"


def test_catalog_version_and_devops_entry() -> None:
    assert CATALOG_VERSION == "cmd-v1.0.0"
    devops = next(cmd for cmd in SYSTEM_COMMANDS if cmd.id == "CMD-PRJ-DEVOPS")
    assert devops.scope == "PROJECT"
    assert "{projectId}" in (devops.route_template or "")
