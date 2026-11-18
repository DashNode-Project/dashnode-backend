"""DTO helpers for the command catalog route."""

from app.orchestration.command_catalog import SYSTEM_COMMANDS
from app.orchestration.command_routes import CommandProjectRef, _to_dto


def test_project_dto_resolves_route_template() -> None:
    template = next(cmd for cmd in SYSTEM_COMMANDS if cmd.id == "CMD-PRJ-DEVOPS")
    project = CommandProjectRef(id="proj-77", name="Alpha")
    dto = _to_dto(
        template,
        role="developer",
        label=f"{template.label} · {project.name}",
        project=project,
    )
    assert dto.route == "/proyectos/proj-77/devops"
    assert dto.label.endswith("Alpha")


def test_home_route_uses_role_segment() -> None:
    template = next(cmd for cmd in SYSTEM_COMMANDS if cmd.id == "CMD-NAV-HOME")
    dto = _to_dto(template, role="manager")
    assert dto.route == "/inicio/gerente"