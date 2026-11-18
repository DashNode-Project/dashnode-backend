"""Integrity checks for the static command catalog (EP-15)."""

import pytest

from app.orchestration.command_catalog import SYSTEM_COMMANDS


@pytest.mark.parametrize("template", SYSTEM_COMMANDS)
def test_each_command_has_keywords_and_id_prefix(template) -> None:
    assert template.id.startswith("CMD-")
    assert len(template.keywords) >= 1


@pytest.mark.parametrize("template", SYSTEM_COMMANDS)
def test_global_commands_declare_route_or_action(template) -> None:
    if template.scope != "GLOBAL":
        return
    assert template.route is not None or template.action is not None


@pytest.mark.parametrize("template", SYSTEM_COMMANDS)
def test_project_commands_declare_route_template(template) -> None:
    if template.scope != "PROJECT":
        return
    assert template.route_template is not None
    assert "{projectId}" in template.route_template
