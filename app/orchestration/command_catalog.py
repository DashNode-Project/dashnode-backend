"""EP-15 static command catalog (cmd-v1.0.0)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CATALOG_VERSION = "cmd-v1.0.0"

CommandType = Literal["PAGE", "ACTION"]
CommandScope = Literal["GLOBAL", "PROJECT"]
UserRole = Literal["admin", "manager", "developer"]


@dataclass(frozen=True)
class CommandTemplate:
    id: str
    label: str
    type: CommandType
    scope: CommandScope
    roles: frozenset[UserRole]
    keywords: tuple[str, ...]
    route: str | None = None
    route_template: str | None = None
    action: str | None = None


_ALL: frozenset[UserRole] = frozenset({"admin", "manager", "developer"})
_MGR_ADMIN: frozenset[UserRole] = frozenset({"admin", "manager"})
_ADMIN: frozenset[UserRole] = frozenset({"admin"})

SYSTEM_COMMANDS: tuple[CommandTemplate, ...] = (
    CommandTemplate(
        "CMD-NAV-HOME",
        "Inicio",
        "PAGE",
        "GLOBAL",
        _ALL,
        ("inicio", "home", "panel"),
        route="/inicio/{roleHome}",
    ),
    CommandTemplate(
        "CMD-NAV-PROJECTS",
        "Proyectos",
        "PAGE",
        "GLOBAL",
        frozenset({"manager", "developer"}),
        ("proyectos", "repositorios"),
        route="/proyectos",
    ),
    CommandTemplate(
        "CMD-NAV-AVAIL",
        "Disponibilidad",
        "PAGE",
        "GLOBAL",
        frozenset({"manager", "developer"}),
        ("disponibilidad", "horarios", "slots"),
        route="/disponibilidad",
    ),
    CommandTemplate(
        "CMD-NAV-MEETINGS",
        "Reuniones",
        "PAGE",
        "GLOBAL",
        frozenset({"manager", "developer"}),
        ("reuniones", "meet", "citas"),
        route="/reuniones",
    ),
    CommandTemplate(
        "CMD-NAV-CAL",
        "Calendario",
        "PAGE",
        "GLOBAL",
        frozenset({"manager", "developer"}),
        ("calendario", "agenda"),
        route="/calendario",
    ),
    CommandTemplate(
        "CMD-NAV-MYTASKS",
        "Mis tareas",
        "PAGE",
        "GLOBAL",
        _ALL,
        ("mis tareas", "pendientes", "asignadas"),
        route="/mis-tareas",
    ),
    CommandTemplate(
        "CMD-NAV-PROFILE",
        "Mi perfil",
        "PAGE",
        "GLOBAL",
        _ALL,
        ("perfil", "cuenta", "avatar"),
        route="/mi-perfil",
    ),
    CommandTemplate(
        "CMD-NAV-MANUAL",
        "Manual de usuario",
        "PAGE",
        "GLOBAL",
        _ALL,
        ("manual", "ayuda", "guía"),
        route="/manual-usuario",
    ),
    CommandTemplate(
        "CMD-NAV-NOTIF",
        "Notificaciones",
        "PAGE",
        "GLOBAL",
        _ALL,
        ("notificaciones", "alertas", "avisos"),
        route="/notificaciones",
    ),
    CommandTemplate(
        "CMD-NAV-USERS",
        "Usuarios",
        "PAGE",
        "GLOBAL",
        _MGR_ADMIN,
        ("usuarios", "personas", "cuentas"),
        route="/usuarios",
    ),
    CommandTemplate(
        "CMD-NAV-ROLES",
        "Permisos y roles",
        "PAGE",
        "GLOBAL",
        _ALL,
        ("permisos", "roles"),
        route="/permisos-y-roles",
    ),
    CommandTemplate(
        "CMD-ACT-ASSISTANT",
        "Abrir asistente de IA",
        "ACTION",
        "GLOBAL",
        _ALL,
        ("asistente", "ia", "copiloto"),
        action="OPEN_ASSISTANT",
    ),
    CommandTemplate(
        "CMD-ACT-NEWPRJ",
        "Nuevo proyecto",
        "ACTION",
        "GLOBAL",
        _MGR_ADMIN,
        ("crear proyecto", "nuevo"),
        route="/proyectos?nuevo=1",
    ),
    CommandTemplate(
        "CMD-PRJ-SUMMARY",
        "Resumen",
        "PAGE",
        "PROJECT",
        _ALL,
        ("resumen", "salud", "health"),
        route_template="/proyectos/{projectId}/resumen",
    ),
    CommandTemplate(
        "CMD-PRJ-TEAM",
        "Equipo",
        "PAGE",
        "PROJECT",
        _ALL,
        ("equipo", "miembros"),
        route_template="/proyectos/{projectId}/equipo",
    ),
    CommandTemplate(
        "CMD-PRJ-MEETINGS",
        "Reuniones del proyecto",
        "PAGE",
        "PROJECT",
        _ALL,
        ("reuniones proyecto",),
        route_template="/proyectos/{projectId}/reuniones",
    ),
    CommandTemplate(
        "CMD-PRJ-TASKS",
        "Tareas: lista",
        "PAGE",
        "PROJECT",
        _ALL,
        ("tareas", "backlog", "lista"),
        route_template="/proyectos/{projectId}/tareas/lista",
    ),
    CommandTemplate(
        "CMD-PRJ-KANBAN",
        "Tareas: Kanban",
        "PAGE",
        "PROJECT",
        _ALL,
        ("kanban", "tablero"),
        route_template="/proyectos/{projectId}/tareas/kanban",
    ),
    CommandTemplate(
        "CMD-PRJ-SPRINTS",
        "Sprints",
        "PAGE",
        "PROJECT",
        _ALL,
        ("sprint", "iteración"),
        route_template="/proyectos/{projectId}/sprints",
    ),
    CommandTemplate(
        "CMD-PRJ-KB",
        "Conocimiento",
        "PAGE",
        "PROJECT",
        _ALL,
        ("conocimiento", "documentación", "kb"),
        route_template="/proyectos/{projectId}/conocimiento",
    ),
    CommandTemplate(
        "CMD-PRJ-ISSUES",
        "Issues",
        "PAGE",
        "PROJECT",
        _ALL,
        ("issues", "fixes", "bugs"),
        route_template="/proyectos/{projectId}/issues",
    ),
    CommandTemplate(
        "CMD-PRJ-NEWFIX",
        "Nuevo fix",
        "ACTION",
        "PROJECT",
        _ALL,
        ("fix", "bug", "nuevo issue"),
        route_template="/proyectos/{projectId}/issues?nuevo=1",
    ),
    CommandTemplate(
        "CMD-PRJ-METRICS",
        "Métricas de IA",
        "PAGE",
        "PROJECT",
        _MGR_ADMIN,
        ("métricas", "ia", "uso"),
        route_template="/proyectos/{projectId}/metricas-ia",
    ),
    CommandTemplate(
        "CMD-PRJ-DEVOPS",
        "DevOps",
        "PAGE",
        "PROJECT",
        _ALL,
        ("devops", "pipeline", "build", "deploy"),
        route_template="/proyectos/{projectId}/devops",
    ),
)


def home_segment(role: str) -> str:
    if role == "admin":
        return "administrador"
    if role == "manager":
        return "gerente"
    return "desarrollador"
