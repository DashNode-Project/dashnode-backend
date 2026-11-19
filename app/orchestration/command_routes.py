"""EP-15: role-filtered command catalog (GET /commands)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository
from app.orchestration.command_catalog import (
    CATALOG_VERSION,
    SYSTEM_COMMANDS,
    CommandTemplate,
    home_segment,
)
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.database import get_db_session

router = APIRouter(prefix="/commands", tags=["commands"])


class CommandProjectRef(BaseModel):
    id: str
    name: str


class CommandItemDTO(BaseModel):
    id: str
    label: str
    type: Literal["PAGE", "ACTION"]
    scope: Literal["GLOBAL", "PROJECT"]
    route: str | None = None
    route_template: str | None = None
    action: str | None = None
    keywords: list[str]
    project: CommandProjectRef | None = None


class CommandCatalogResponse(BaseModel):
    catalog_version: str
    commands: list[CommandItemDTO]
    projects: list[CommandProjectRef]


def _allowed(template: CommandTemplate, role: str) -> bool:
    return role in template.roles


def _to_dto(
    template: CommandTemplate,
    *,
    role: str,
    label: str | None = None,
    project: CommandProjectRef | None = None,
) -> CommandItemDTO:
    route = template.route
    if route and "{roleHome}" in route:
        route = route.replace("{roleHome}", home_segment(role))
    elif template.route_template and project is not None:
        route = template.route_template.replace("{projectId}", project.id)
    return CommandItemDTO(
        id=template.id if project is None else f"{template.id}:{project.id}",
        label=label or template.label,
        type=template.type,
        scope=template.scope,
        route=route,
        route_template=template.route_template if project is None else None,
        action=template.action,
        keywords=list(template.keywords),
        project=project,
    )


@router.get("", response_model=CommandCatalogResponse)
def list_commands(
    response: Response,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CommandCatalogResponse:
    response.headers["Cache-Control"] = "no-store"
    repo = SqlAlchemyProjectRepository(db)
    projects = repo.list_visible_for_user(actor.id, role=actor.role)
    project_refs = [CommandProjectRef(id=p.id, name=p.name) for p in projects]

    items: list[CommandItemDTO] = []
    for template in SYSTEM_COMMANDS:
        if template.scope == "GLOBAL" and _allowed(template, actor.role):
            items.append(_to_dto(template, role=actor.role))
        elif template.scope == "PROJECT" and _allowed(template, actor.role):
            for project in project_refs:
                suffix_label = f"{template.label} · {project.name}"
                items.append(
                    _to_dto(
                        template,
                        role=actor.role,
                        label=suffix_label,
                        project=project,
                    )
                )

    return CommandCatalogResponse(
        catalog_version=CATALOG_VERSION,
        commands=items,
        projects=project_refs,
    )
