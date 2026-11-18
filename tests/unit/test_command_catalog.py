"""Command catalog helpers (EP-15)."""

from app.orchestration.command_catalog import home_segment


def test_home_segment_per_role() -> None:
    assert home_segment("admin") == "administrador"
    assert home_segment("manager") == "gerente"
    assert home_segment("developer") == "desarrollador"