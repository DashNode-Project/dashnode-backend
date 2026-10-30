"""Idempotent demo dataset: NovaTech - Plataforma de Gestion Empresarial.

Run from backend root:
  python scripts/seed_novatech_demo.py

Uses SEED_MANAGER_EMAIL (from .env) as project manager/owner when present.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth.infrastructure.models import UserModel
from app.modules.availability.infrastructure.models import MeetingModel, MeetingParticipantModel
from app.modules.backlog.infrastructure.models import EpicModel, StoryTaskModel, UserStoryModel
from app.modules.documentation.domain.entities import DocumentationApprovalStatus
from app.modules.documentation.infrastructure.models import DocumentationEntryModel
from app.modules.projects.domain.entities import ProjectStatus
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.modules.sprints.infrastructure.models import SprintModel
from app.shared.infrastructure.database import SessionLocal
from app.shared.infrastructure.id_generator import UuidGenerator

PROJECT_NAME = "NovaTech - Plataforma de Gestion Empresarial"
id_gen = UuidGenerator()


def _manager(db: Session) -> UserModel:
    email = settings.SEED_MANAGER_EMAIL
    user = db.query(UserModel).filter_by(email=email).first()
    if user is None:
        raise RuntimeError(f"Manager seed user not found: {email}")
    return user


_TASK_TYPES = ("frontend", "backend", "qa", "documentacion", "devops")


def _repair_global_invalid_enums(db: Session) -> None:
    valid_status = {item.value for item in ProjectStatus}
    for project in db.query(ProjectModel).filter(ProjectModel.deleted_at.is_(None)).all():
        if project.status not in valid_status:
            project.status = ProjectStatus.ACTIVO.value

    for task in db.scalars(
        select(StoryTaskModel).where(StoryTaskModel.task_type == "development")
    ).all():
        task.task_type = "backend"

    for story in db.scalars(
        select(UserStoryModel).where(UserStoryModel.moscow_priority == "must")
    ).all():
        story.moscow_priority = "must_have"


def _repair_novatech_integrity(db: Session, project: ProjectModel) -> None:
    """Fix invalid enum values written by earlier seed versions."""
    repaired = False
    valid_status = {item.value for item in ProjectStatus}
    if project.status not in valid_status:
        project.status = ProjectStatus.ACTIVO.value
        repaired = True

    for sprint in db.scalars(select(SprintModel).where(SprintModel.project_id == project.id)).all():
        if sprint.status == "PLANNED":
            sprint.status = "PLANNING"
            repaired = True

    for story in db.scalars(
        select(UserStoryModel).where(UserStoryModel.project_id == project.id)
    ).all():
        if story.moscow_priority == "must":
            story.moscow_priority = "must_have"
            repaired = True

    for index, task in enumerate(
        db.scalars(select(StoryTaskModel).where(StoryTaskModel.project_id == project.id)).all()
    ):
        if task.task_type == "development":
            task.task_type = _TASK_TYPES[index % len(_TASK_TYPES)]
            repaired = True

    if repaired:
        print(f"[repair] Domain values normalized for {project.name} ({project.id})")


def _ensure_project(db: Session, manager: UserModel) -> ProjectModel:
    existing = db.query(ProjectModel).filter_by(name=PROJECT_NAME, deleted_at=None).first()
    if existing is not None:
        print(f"[skip] Project already exists: {PROJECT_NAME} ({existing.id})")
        return existing
    now = datetime.now(UTC)
    project = ProjectModel(
        id=id_gen.generate(),
        name=PROJECT_NAME,
        description=(
            "Escenario de demostración integral para DashNode y el asistente IA: "
            "gestión empresarial con usuarios, proyectos, tareas, reuniones y documentación."
        ),
        owner_id=manager.id,
        manager_id=manager.id,
        priority="alta",
        tech_stack='["FastAPI","React","PostgreSQL"]',
        meeting_link="https://meet.example/novatech",
        status=ProjectStatus.ACTIVO.value,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectMemberModel(
            project_id=project.id,
            user_id=manager.id,
            role="manager",
            joined_at=now,
        )
    )
    dev = db.query(UserModel).filter_by(role="developer").first()
    if dev and dev.id != manager.id:
        db.add(
            ProjectMemberModel(
                project_id=project.id,
                user_id=dev.id,
                role="developer",
                joined_at=now,
            )
        )
    print(f"[ok] Created project {PROJECT_NAME}")
    return project


def _seed_backlog(db: Session, project: ProjectModel, manager: UserModel) -> None:
    if db.query(EpicModel).filter_by(project_id=project.id).first() is not None:
        print("[skip] Backlog already seeded")
        return
    now = datetime.now(UTC)
    today = datetime.now(UTC).date()
    sprint1 = SprintModel(
        id=id_gen.generate(),
        project_id=project.id,
        name="Sprint 1 - Planificacion y desarrollo inicial",
        goal="Fundamentos de autenticación y proyectos",
        start_date=today - timedelta(days=14),
        end_date=today + timedelta(days=1),
        status="ACTIVE",
        created_at=now,
    )
    sprint2 = SprintModel(
        id=id_gen.generate(),
        project_id=project.id,
        name="Sprint 2 - Integracion y funciones complementarias",
        goal="Tareas, reuniones y documentación",
        start_date=today + timedelta(days=2),
        end_date=today + timedelta(days=16),
        status="PLANNING",
        created_at=now,
    )
    db.add_all([sprint1, sprint2])
    db.flush()
    epics = [
        ("EP-01", "Gestión de usuarios y autenticación"),
        ("EP-02", "Gestión de proyectos y equipos"),
        ("EP-03", "Gestión de tareas y seguimiento"),
        ("EP-04", "Reuniones y documentación"),
    ]
    stories_template = {
        "EP-01": [
            ("Registro de usuarios", "visitante", "crear una cuenta", "Validación de email"),
            ("Inicio de sesión", "usuario", "acceder con credenciales", "JWT emitido"),
            ("Recuperación de contraseña", "usuario", "restablecer acceso", "Enlace expira"),
            ("Gestión de perfiles", "usuario", "actualizar mis datos", "Campos obligatorios"),
            ("Administración de roles", "administrador", "asignar permisos", "RBAC aplicado"),
        ],
        "EP-02": [
            ("Crear proyectos", "manager", "registrar un proyecto", "Estado inicial válido"),
            ("Consultar proyectos", "manager", "ver mis proyectos", "Lista filtrada por rol"),
            ("Editar información", "manager", "actualizar descripción", "Auditoría registrada"),
            ("Asignar miembros", "manager", "invitar al equipo", "Roles coherentes"),
            ("Responsabilidades del equipo", "manager", "ver roles", "Matriz visible"),
        ],
        "EP-03": [
            ("Crear tareas", "developer", "desglosar una HU", "Vinculada a HU"),
            ("Asignar responsables", "manager", "delegar trabajo", "Notificación interna"),
            ("Actualizar estados", "developer", "reflejar avance", "Kanban consistente"),
            ("Prioridades y fechas", "manager", "planificar entregas", "Fechas ISO"),
            ("Consultar avance", "manager", "medir progreso", "Métricas por sprint"),
        ],
        "EP-04": [
            ("Programar reuniones", "manager", "coordinar encuentros", "Participantes invitados"),
            ("Invitar participantes", "manager", "confirmar asistencia", "Estados de respuesta"),
            ("Consultar reuniones", "developer", "ver agenda", "Filtros por estado"),
            (
                "Adjuntar documentación",
                "manager",
                "centralizar conocimiento",
                "Metadatos completos",
            ),
            ("Descargar documentos", "developer", "acceder a archivos", "Permisos respetados"),
        ],
    }
    sprint_cycle = [sprint1.id, sprint1.id, sprint1.id, sprint2.id, sprint2.id]
    story_idx = 0
    for code, epic_name in epics:
        epic = EpicModel(
            id=id_gen.generate(),
            project_id=project.id,
            name=f"{code} — {epic_name}",
            description=epic_name,
            color="#6366F1",
            sort_order=story_idx,
            created_by=manager.id,
            created_at=now,
            updated_at=now,
        )
        db.add(epic)
        for title, role, reason, criteria in stories_template[code]:
            sprint_id = sprint_cycle[story_idx % len(sprint_cycle)]
            story = UserStoryModel(
                id=id_gen.generate(),
                epic_id=epic.id,
                project_id=project.id,
                title=title,
                user_role=role,
                reason=f"Quiero {reason} para operar en NovaTech.",
                acceptance_criteria=f"Dado el contexto, {criteria}.",
                moscow_priority="must_have",
                story_points=3,
                estimation_mode="story",
                sprint_id=sprint_id,
                sort_order=story_idx,
                created_by=manager.id,
                created_at=now,
                updated_at=now,
                label=f"{code}-HU-{story_idx + 1:02d}",
            )
            db.add(story)
            db.add(
                StoryTaskModel(
                    id=id_gen.generate(),
                    user_story_id=story.id,
                    project_id=project.id,
                    name=f"Tarea: {title}",
                    task_type=_TASK_TYPES[story_idx % len(_TASK_TYPES)],
                    notes="Generada para escenario NovaTech",
                    status=["TODO", "IN_PROGRESS", "DONE", "TESTING"][story_idx % 4],
                    assignee_id=manager.id,
                    estimated_hours=Decimal("4.0"),
                    logged_hours=Decimal("0"),
                    created_by=manager.id,
                    created_at=now,
                    updated_at=now,
                )
            )
            story_idx += 1
    print("[ok] Epics, 20 HUs and tasks")


def _seed_meetings(db: Session, project: ProjectModel, manager: UserModel) -> None:
    if db.query(MeetingModel).filter_by(project_id=project.id).first() is not None:
        print("[skip] Meetings already seeded")
        return
    now = datetime.now(UTC)
    today = datetime.now(UTC).date()
    scenarios = [
        ("Daily NovaTech", "scheduled", today + timedelta(days=1), "09:00", "09:15"),
        ("Planning Sprint 2", "scheduled", today + timedelta(days=3), "15:00", "16:00"),
        ("Review Sprint 1", "completed", today - timedelta(days=1), "11:00", "12:00"),
        ("Sync cancelada", "cancelled", today + timedelta(days=5), "10:00", "10:30"),
    ]
    dev = db.query(UserModel).filter_by(role="developer").first()
    for title, status, when, start, end in scenarios:
        meeting = MeetingModel(
            id=id_gen.generate(),
            project_id=project.id,
            title=title,
            type="General",
            description=f"Reunión demo {title}",
            date=when.isoformat(),
            start_time=start,
            end_time=end,
            duration=60,
            link="https://meet.example/novatech-room",
            status=status,
            creator_id=manager.id,
            created_at=now,
            updated_at=now,
        )
        db.add(meeting)
        for uid in {manager.id, dev.id if dev else manager.id}:
            db.add(
                MeetingParticipantModel(
                    meeting_id=meeting.id,
                    user_id=uid,
                    response="pendiente" if status == "scheduled" else "aceptada",
                )
            )
    print("[ok] Meetings")


def _seed_docs(db: Session, project: ProjectModel, manager: UserModel) -> None:
    if db.query(DocumentationEntryModel).filter_by(project_id=project.id).first() is not None:
        print("[skip] Documentation already seeded")
        return
    now = datetime.now(UTC)
    docs = [
        (
            "Documento de arquitectura de software",
            "Arquitectura",
            "Capas API FastAPI, frontend React, PostgreSQL. Componentes: auth, projects, backlog, AI.",
        ),
        (
            "Especificación de requisitos",
            "Requisitos",
            "Requisitos funcionales para gestión empresarial, RBAC y trazabilidad sprint-HU-tarea.",
        ),
        (
            "Planificación del proyecto NovaTech",
            "Planificación",
            "Roadmap en 2 sprints con entregables de autenticación, proyectos y documentación.",
        ),
        (
            "Acta de reunion - Kickoff",
            "Actas",
            "Se acordó alcance MVP, roles del equipo y fechas de sprint.",
        ),
    ]
    for title, category, content in docs:
        db.add(
            DocumentationEntryModel(
                id=id_gen.generate(),
                project_id=project.id,
                author_id=manager.id,
                title=title,
                category=category,
                objective=content[:200],
                tags="novatech,demo",
                content=content,
                external_url=None,
                approval_status=DocumentationApprovalStatus.APPROVED.value,
                is_pinned=False,
                is_visible_to_devs=True,
                rejection_reason=None,
                is_deleted=False,
                created_at=now,
                updated_at=now,
            )
        )
    print("[ok] Documentation entries")


def main() -> None:
    db = SessionLocal()
    try:
        _repair_global_invalid_enums(db)
        manager = _manager(db)
        project = _ensure_project(db, manager)
        _repair_novatech_integrity(db, project)
        for orphan in db.query(ProjectModel).filter(
            ProjectModel.name == PROJECT_NAME,
            ProjectModel.deleted_at.is_(None),
            ProjectModel.id != project.id,
        ):
            _repair_novatech_integrity(db, orphan)
        _seed_backlog(db, project, manager)
        _seed_meetings(db, project, manager)
        _seed_docs(db, project, manager)
        db.commit()
        print(f"NovaTech demo ready for manager {manager.email} (project id={project.id})")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
