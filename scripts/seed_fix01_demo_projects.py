"""FIX-01: two demo projects (Helix Health + OrbitLogistics) for Manager smoke tests."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
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
from app.modules.fixes.infrastructure.models import FixModel
from app.modules.projects.domain.entities import ProjectStatus
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.modules.sprints.infrastructure.models import SprintModel
from app.shared.infrastructure.database import SessionLocal, initialize_database
from app.shared.infrastructure.id_generator import UuidGenerator

DEMO_PROJECTS: list[dict[str, str]] = [
    {
        "name": "Helix Health Portal",
        "description": "Portal clínico para citas, historias y telemedicina.",
        "domain": "salud",
        "stack": '["React","FastAPI","PostgreSQL","HL7 FHIR"]',
        "meeting": "https://meet.example/helix-daily",
    },
    {
        "name": "OrbitLogistics TMS",
        "description": "Sistema de transporte y ruteo para cadena de suministro.",
        "domain": "logistica",
        "stack": '["Vue","FastAPI","PostgreSQL","MQTT"]',
        "meeting": "https://meet.example/orbit-planning",
    },
]

id_gen = UuidGenerator()
_TASK_TYPES = ("frontend", "backend", "qa", "documentacion", "devops")
_STATUSES = ("TODO", "IN_PROGRESS", "DONE", "TESTING")


def _manager(db: Session) -> UserModel:
    email = settings.SEED_MANAGER_EMAIL
    user = db.query(UserModel).filter_by(email=email).first()
    if user is None:
        raise RuntimeError(f"Manager seed user not found: {email}")
    return user


def _ensure_members(db: Session, project: ProjectModel, manager: UserModel) -> None:
    now = datetime.now(UTC)
    existing = set(
        db.scalars(
            select(ProjectMemberModel.user_id).where(ProjectMemberModel.project_id == project.id)
        ).all()
    )
    if manager.id not in existing:
        db.add(
            ProjectMemberModel(
                project_id=project.id,
                user_id=manager.id,
                role="manager",
                joined_at=now,
            )
        )
    dev = db.query(UserModel).filter_by(role="developer").first()
    if dev and dev.id not in existing:
        db.add(
            ProjectMemberModel(
                project_id=project.id,
                user_id=dev.id,
                role="developer",
                joined_at=now,
            )
        )


def _ensure_project(db: Session, manager: UserModel, spec: dict[str, str]) -> ProjectModel:
    existing = db.query(ProjectModel).filter_by(name=spec["name"], deleted_at=None).first()
    if existing:
        print(f"[skip] Project exists: {spec['name']} ({existing.id})")
        _ensure_members(db, existing, manager)
        return existing
    now = datetime.now(UTC)
    project = ProjectModel(
        id=id_gen.generate(),
        name=spec["name"],
        description=spec["description"],
        owner_id=manager.id,
        manager_id=manager.id,
        priority="alta",
        tech_stack=spec["stack"],
        meeting_link=spec["meeting"],
        status=ProjectStatus.ACTIVO.value,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.flush()
    _ensure_members(db, project, manager)
    print(f"[ok] Created {spec['name']}")
    return project


def _seed_sprints_and_backlog(db: Session, project: ProjectModel, manager: UserModel) -> None:
    if db.query(SprintModel).filter_by(project_id=project.id).first():
        print(f"[skip] Backlog for {project.name}")
        return
    now = datetime.now(UTC)
    today = date.today()
    sprints: list[SprintModel] = []
    for i in range(4):
        start = today + timedelta(days=-28 + i * 14)
        end = start + timedelta(days=13)
        status = ("CLOSED", "CLOSED", "ACTIVE", "PLANNING")[i]
        sprints.append(
            SprintModel(
                id=id_gen.generate(),
                project_id=project.id,
                name=f"Sprint {i + 1}",
                goal=f"Entrega {i + 1} — {project.name}",
                start_date=start,
                end_date=end,
                status=status,
                created_at=now,
            )
        )
    db.add_all(sprints)
    db.flush()
    epic = EpicModel(
        id=id_gen.generate(),
        project_id=project.id,
        name="EP-01 — Core",
        description="Funcionalidades núcleo del dominio",
        color="#3B82F6",
        sort_order=0,
        created_by=manager.id,
        created_at=now,
        updated_at=now,
    )
    db.add(epic)
    db.flush()
    story_order = 0
    for sprint in sprints:
        for hu in range(6):
            story_order += 1
            pts = 2 + (story_order % 5)
            st = _STATUSES[story_order % len(_STATUSES)]
            story = UserStoryModel(
                id=id_gen.generate(),
                epic_id=epic.id,
                project_id=project.id,
                title=f"HU {story_order}: capacidad {hu + 1} sprint {sprint.name}",
                user_role="manager",
                reason=f"Necesito entregar valor en {project.name}.",
                acceptance_criteria="- Criterio observable\n- Pruebas de aceptación",
                definition_of_ready="## DoR\n- Alcance claro\n- Dependencias resueltas",
                definition_of_done="## DoD\n- Código revisado\n- Demo lista",
                moscow_priority=["must_have", "should_have", "could_have"][story_order % 3],
                story_points=pts,
                estimation_mode="story",
                sprint_id=sprint.id,
                sort_order=story_order,
                created_by=manager.id,
                created_at=now,
                updated_at=now,
                label=f"HU-{story_order:03d}",
            )
            db.add(story)
            db.flush()
            for t in range(4 + (story_order % 2)):
                db.add(
                    StoryTaskModel(
                        id=id_gen.generate(),
                        user_story_id=story.id,
                        project_id=project.id,
                        name=f"Tarea {t + 1} — {story.title[:40]}",
                        task_type=_TASK_TYPES[(story_order + t) % len(_TASK_TYPES)],
                        notes="Demo FIX-01",
                        status=st if t < 2 else _STATUSES[(story_order + t) % len(_STATUSES)],
                        assignee_id=manager.id,
                        estimated_hours=Decimal("3.5"),
                        story_points=1,
                        logged_hours=Decimal("0"),
                        created_by=manager.id,
                        created_at=now,
                        updated_at=now,
                    )
                )
    print(f"[ok] 4 sprints, 24 HUs, tasks for {project.name}")


def _seed_meetings(db: Session, project: ProjectModel, manager: UserModel) -> None:
    if db.query(MeetingModel).filter_by(project_id=project.id).first():
        return
    now = datetime.now(UTC)
    today = date.today()
    for idx, (title, when, status) in enumerate(
        [
            ("Kickoff", today - timedelta(days=7), "completed"),
            ("Planning próximo", today + timedelta(days=5), "scheduled"),
        ]
    ):
        m = MeetingModel(
            id=id_gen.generate(),
            project_id=project.id,
            title=title,
            type="General",
            description=f"Reunión demo {project.name}",
            date=when.isoformat(),
            start_time="10:00",
            end_time="11:00",
            duration=60,
            link=project.meeting_link,
            status=status,
            creator_id=manager.id,
            created_at=now,
            updated_at=now,
        )
        db.add(m)
        db.add(
            MeetingParticipantModel(
                meeting_id=m.id,
                user_id=manager.id,
                response="aceptada",
            )
        )
    print(f"[ok] Meetings for {project.name}")


def _seed_docs(db: Session, project: ProjectModel, manager: UserModel) -> None:
    if db.query(DocumentationEntryModel).filter_by(project_id=project.id).first():
        return
    now = datetime.now(UTC)
    for i, (title, cat) in enumerate(
        [
            ("Arquitectura", "Técnica"),
            ("Requisitos", "Funcional"),
            ("Manual operativo", "General"),
            ("Acta kickoff", "Reunión"),
        ]
    ):
        db.add(
            DocumentationEntryModel(
                id=id_gen.generate(),
                project_id=project.id,
                author_id=manager.id,
                title=title,
                category=cat,
                objective=f"Documentación {i + 1} — {project.name}",
                tags="fix01,demo",
                content=f"Contenido demo para **{project.name}** ({title}).",
                approval_status=DocumentationApprovalStatus.APPROVED.value,
                is_pinned=False,
                is_visible_to_devs=True,
                is_deleted=False,
                created_at=now,
                updated_at=now,
            )
        )
    print(f"[ok] Docs for {project.name}")


def _seed_issues(db: Session, project: ProjectModel, manager: UserModel) -> None:
    if db.query(FixModel).filter_by(project_id=project.id).first():
        return
    now = datetime.now(UTC)
    for i, (title, st) in enumerate(
        [("Error validación formulario", "open"), ("Timeout API externa", "open")]
    ):
        db.add(
            FixModel(
                id=id_gen.generate(),
                project_id=project.id,
                title=title,
                description=f"Issue demo {i + 1} en {project.name}",
                severity="medium",
                type="bug",
                status=st,
                reporter_id=manager.id,
                assignee_id=manager.id,
                created_at=now,
                updated_at=now,
            )
        )
    print(f"[ok] Issues for {project.name}")


def main() -> None:
    initialize_database()
    with SessionLocal() as db:
        manager = _manager(db)
        for spec in DEMO_PROJECTS:
            project = _ensure_project(db, manager, spec)
            _seed_sprints_and_backlog(db, project, manager)
            _seed_meetings(db, project, manager)
            _seed_docs(db, project, manager)
            _seed_issues(db, project, manager)
        db.commit()
        print("[ok] FIX-01 demo projects ready for", manager.email)


if __name__ == "__main__":
    main()