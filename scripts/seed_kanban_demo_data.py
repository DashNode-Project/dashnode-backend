"""Seed realistic demo data for EP-08 Kanban Board and all roles in local PostgreSQL.

Creates/updates:
1. Users: admin, manager, developer, dev2 (developer 2), ivana@gmail.com
2. Demo Project 1: 'Segundo proyecto' (or 'Proyecto Kanban EP-08') with:
   - Full membership for all accounts
   - Active Sprint 'Sprint 1 - Épica Kanban'
   - Epics and User Stories
   - 10 Tasks distributed across all 6 columns:
     * TODO: Tarea Frontend (Dev 1), Tarea Backend (Dev 2), Tarea con Predecesora (Dev 1)
     * IN_PROGRESS: Tarea Drag&Drop (Dev 1), Tarea Webhooks (Dev 2), Tarea con Impedimento (Dev 1)
     * CODE_REVIEW: Tarea PR Backlog (Dev 1)
     * TESTING: Tarea Pruebas Regresión (Dev 1)
     * CORRECTION: Tarea Bug Fix (Dev 1)
     * DONE: Tarea DB Migración (Dev 2)
   - WIP Limits configured on IN_PROGRESS (limit 2 -> triggers exceeded alert 3/2), CODE_REVIEW (limit 2), TESTING (limit 2)
3. Demo Project 2: 'Proyecto Sin Sprint Activo' for verifying HU-72 empty sprint state.
"""

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.modules.auth.infrastructure.models import UserModel
from app.modules.backlog.infrastructure.models import EpicModel, StoryTaskModel, UserStoryModel
from app.modules.kanban.infrastructure.models import KanbanColumnSettingsModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.modules.sprints.infrastructure.models import SprintModel
from app.shared.infrastructure.database import SessionLocal
from app.shared.infrastructure.hasher import Argon2PasswordHasher
from app.shared.infrastructure.id_generator import UuidGenerator

id_gen = UuidGenerator()
hasher = Argon2PasswordHasher()
now = datetime.now(UTC)
today = now.date()


def get_or_create_user(db, email: str, role: str, name: str, password_plain: str) -> UserModel:
    user = db.query(UserModel).filter_by(email=email).first()
    if user is None:
        user = UserModel(
            id=id_gen.generate(),
            email=email,
            name=name,
            role=role,
            hashed_password=hasher.hash(password_plain),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()
        print(f"[+] Usuario creado: {name} ({email}) - Rol: {role}")
    else:
        # Ensure user is active and role is correct
        user.is_active = True
        user.name = name
        user.role = role
        db.flush()
        print(f"[=] Usuario existente: {name} ({email}) - Rol: {role}")
    return user


def ensure_member(db, project_id: str, user_id: str, role: str = "member"):
    member = db.query(ProjectMemberModel).filter_by(project_id=project_id, user_id=user_id).first()
    if member is None:
        db.add(ProjectMemberModel(project_id=project_id, user_id=user_id, role=role, joined_at=now))
        db.flush()
        print(f"    [+] Miembro agregado: {user_id} ({role})")


def seed_kanban_data():
    db = SessionLocal()
    try:
        print("\n" + "=" * 70)
        print(" INICIANDO POBLADO DE DATOS DE PRUEBA PARA TABLERO KANBAN (EP-08)")
        print("=" * 70)

        # 1. Asegurar usuarios de prueba
        admin = get_or_create_user(
            db,
            "admin@dashnode.local",
            "admin",
            "Administrador Principal",
            "na7225oJ05vrXKu_VEW8aZ7",
        )
        manager = get_or_create_user(
            db,
            "manager@dashnode.local",
            "manager",
            "Gerente Carlos Mendoza",
            "0FogNyGZsssWGaCw2fcZaZ7",
        )
        dev1 = get_or_create_user(
            db, "developer@dashnode.local", "developer", "Dev Juan Pérez", "sWD9wQEws21bGreRfhfuaZ7"
        )
        dev2 = get_or_create_user(
            db, "dev2@dashnode.local", "developer", "Dev María García", "sWD9wQEws21bGreRfhfuaZ7"
        )

        # Usuario personalizado ivana@gmail.com si existe
        ivana = db.query(UserModel).filter_by(email="ivana@gmail.com").first()
        if ivana:
            print(f"[=] Usuario personal detectado: {ivana.name} ({ivana.email})")

        all_users = [admin, manager, dev1, dev2]
        if ivana:
            all_users.append(ivana)

        # 2. Proyecto Principal Kanban
        project = (
            db.query(ProjectModel)
            .filter(
                ProjectModel.name.in_(
                    ["Proyecto Kanban EP-08", "Segundo proyecto", "DashNode Initial Project"]
                )
            )
            .order_by(ProjectModel.created_at.desc())
            .first()
        )
        if project is None:
            project = ProjectModel(
                id=id_gen.generate(),
                name="Proyecto Kanban EP-08",
                description="Proyecto de demostración para Tablero Kanban, límites WIP y bloqueos",
                owner_id=manager.id,
                manager_id=manager.id,
                priority="alta",
                tech_stack='["React", "FastAPI", "PostgreSQL", "TailwindCSS"]',
                meeting_link="https://meet.google.com/kanban-demo",
                status="activo",
                created_at=now,
                updated_at=now,
            )
            db.add(project)
            db.flush()
            print(f"[+] Proyecto creado: {project.name} ({project.id})")
        else:
            project.name = "Proyecto Kanban EP-08"
            project.description = (
                "Proyecto de demostración para Tablero Kanban, límites WIP y bloqueos"
            )
            project.manager_id = manager.id
            db.flush()
            print(f"[=] Usando proyecto existente: {project.name} ({project.id})")

        # Vincular a todos los usuarios como miembros
        for u in all_users:
            m_role = "lead" if u.role in ["admin", "manager"] else "member"
            ensure_member(db, project.id, u.id, m_role)

        # 3. Épica
        epic = (
            db.query(EpicModel)
            .filter_by(project_id=project.id, name="Épica 08: Tablero Kanban")
            .first()
        )
        if epic is None:
            epic = EpicModel(
                id=id_gen.generate(),
                project_id=project.id,
                name="Épica 08: Tablero Kanban",
                description="Flujo de trabajo visual, límites WIP y gestión de impedimentos",
                color="#3B82F6",
                sort_order=1,
                created_by=manager.id,
                created_at=now,
                updated_at=now,
            )
            db.add(epic)
            db.flush()
            print(f"[+] Épica creada: {epic.name}")

        # 4. Sprint Activo
        sprint = db.query(SprintModel).filter_by(project_id=project.id, status="ACTIVE").first()
        if sprint is None:
            sprint = SprintModel(
                id=id_gen.generate(),
                project_id=project.id,
                name="Sprint 1 - Tablero Kanban",
                goal="Completar la visualización del tablero, control de WIP y gestión de bloqueos",
                start_date=today - timedelta(days=2),
                end_date=today + timedelta(days=12),
                status="ACTIVE",
                created_at=now,
            )
            db.add(sprint)
            db.flush()
            print(f"[+] Sprint activo creado: {sprint.name} ({sprint.id})")
        else:
            sprint.name = "Sprint 1 - Tablero Kanban"
            sprint.goal = (
                "Completar la visualización del tablero, control de WIP y gestión de bloqueos"
            )
            db.flush()
            print(f"[=] Sprint activo existente: {sprint.name} ({sprint.id})")

        # 5. Historias de Usuario
        def get_or_create_story(title: str, label: str) -> UserStoryModel:
            st = db.query(UserStoryModel).filter_by(project_id=project.id, title=title).first()
            if st is None:
                st = UserStoryModel(
                    id=id_gen.generate(),
                    epic_id=epic.id,
                    project_id=project.id,
                    title=title,
                    user_role="Desarrollador / Gerente",
                    reason="optimizar la trazabilidad y flujo ágil",
                    acceptance_criteria="Visualización de columnas, tarjetas y restricciones de rol",
                    moscow_priority="must_have",
                    story_points=8,
                    estimation_mode="story",
                    sprint_id=sprint.id,
                    label=label,
                    created_by=manager.id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(st)
                db.flush()
                print(f"[+] Historia creada: [{label}] {title}")
            else:
                st.sprint_id = sprint.id
                db.flush()
            return st

        story_kanban = get_or_create_story("Gestión de Flujo y Columnas Kanban", "HU-72-73")
        story_wip = get_or_create_story("Límites de Trabajo en Progreso (WIP)", "HU-74")
        story_block = get_or_create_story("Gestión de Impedimentos y Dependencias", "HU-76")

        # 6. Tareas de Historias de Usuario (Story Tasks)
        # Limpiar tareas previas de demostración para evitar duplicados en este sprint
        existing_tasks = db.query(StoryTaskModel).filter_by(project_id=project.id).all()
        existing_task_map = {t.name: t for t in existing_tasks}

        tasks_to_create = [
            # Tareas en TODO
            {
                "name": "Diseñar componentes visuales de tarjetas Kanban",
                "story_id": story_kanban.id,
                "task_type": "frontend",
                "status": "TODO",
                "assignee_id": dev1.id,
                "estimated_hours": Decimal("6.0"),
                "logged_hours": Decimal("0.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": None,
            },
            {
                "name": "Especificación OpenAPI y contratos para métricas de flujo",
                "story_id": story_kanban.id,
                "task_type": "backend",
                "status": "TODO",
                "assignee_id": dev2.id,
                "estimated_hours": Decimal("8.0"),
                "logged_hours": Decimal("0.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": None,
            },
            # Tareas en IN_PROGRESS (generan un total de 3 tareas para validar límite WIP de 2)
            {
                "name": "Implementar Drag and Drop en columnas del tablero",
                "story_id": story_kanban.id,
                "task_type": "frontend",
                "status": "IN_PROGRESS",
                "assignee_id": dev1.id,
                "estimated_hours": Decimal("12.0"),
                "logged_hours": Decimal("4.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": None,
            },
            {
                "name": "Sincronización de eventos de WebSocket en tiempo real",
                "story_id": story_kanban.id,
                "task_type": "backend",
                "status": "IN_PROGRESS",
                "assignee_id": dev2.id,
                "estimated_hours": Decimal("10.0"),
                "logged_hours": Decimal("5.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": None,
            },
            # Tarea Bloqueada por Impedimento (HU-76) en IN_PROGRESS
            {
                "name": "Integración con API de pasarela de pagos externa",
                "story_id": story_block.id,
                "task_type": "backend",
                "status": "IN_PROGRESS",
                "assignee_id": dev1.id,
                "estimated_hours": Decimal("16.0"),
                "logged_hours": Decimal("2.0"),
                "is_blocked": True,
                "blocked_reason": "Esperando credenciales Sandbox de producción del proveedor externo",
                "blocked_by": None,
            },
            # Tarea con Predecesora Bloqueante (HU-76) en TODO
            {
                "name": "Despliegue de servicio en ambiente de pruebas (Staging)",
                "story_id": story_block.id,
                "task_type": "devops",
                "status": "TODO",
                "assignee_id": dev1.id,
                "estimated_hours": Decimal("5.0"),
                "logged_hours": Decimal("0.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": "Sincronización de eventos de WebSocket en tiempo real",  # Depende de la tarea de WebSockets
            },
            # Tarea en CODE_REVIEW
            {
                "name": "Pull Request: Optimización de consultas de tablero y caché",
                "story_id": story_kanban.id,
                "task_type": "backend",
                "status": "CODE_REVIEW",
                "assignee_id": dev1.id,
                "estimated_hours": Decimal("4.0"),
                "logged_hours": Decimal("4.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": None,
            },
            # Tarea en TESTING
            {
                "name": "Pruebas de regresión y cobertura de límites WIP",
                "story_id": story_wip.id,
                "task_type": "qa",
                "status": "TESTING",
                "assignee_id": dev1.id,
                "estimated_hours": Decimal("8.0"),
                "logged_hours": Decimal("6.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": None,
            },
            # Tarea en CORRECTION (Protegida HU-73)
            {
                "name": "Fix: Ajuste en padding móvil de columnas Kanban",
                "story_id": story_kanban.id,
                "task_type": "frontend",
                "status": "CORRECTION",
                "assignee_id": dev1.id,
                "estimated_hours": Decimal("3.0"),
                "logged_hours": Decimal("1.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": None,
            },
            # Tarea en DONE
            {
                "name": "Creación de modelo de datos KanbanColumnSettingsModel",
                "story_id": story_wip.id,
                "task_type": "bd",
                "status": "DONE",
                "assignee_id": dev2.id,
                "estimated_hours": Decimal("4.0"),
                "logged_hours": Decimal("4.0"),
                "is_blocked": False,
                "blocked_reason": None,
                "blocked_by": None,
            },
        ]

        created_tasks_dict = {}

        # Primer pase: crear o actualizar tareas
        for item in tasks_to_create:
            t_name = item["name"]
            task = existing_task_map.get(t_name)
            if task is None:
                task = StoryTaskModel(
                    id=id_gen.generate(),
                    user_story_id=item["story_id"],
                    project_id=project.id,
                    name=t_name,
                    task_type=item["task_type"],
                    notes="Generado automáticamente para pruebas locales de QA",
                    status=item["status"],
                    assignee_id=item["assignee_id"],
                    estimated_hours=item["estimated_hours"],
                    logged_hours=item["logged_hours"],
                    is_blocked=item["is_blocked"],
                    blocked_reason=item["blocked_reason"],
                    created_by=manager.id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(task)
            else:
                task.user_story_id = item["story_id"]
                task.task_type = item["task_type"]
                task.status = item["status"]
                task.assignee_id = item["assignee_id"]
                task.estimated_hours = item["estimated_hours"]
                task.logged_hours = item["logged_hours"]
                task.is_blocked = item["is_blocked"]
                task.blocked_reason = item["blocked_reason"]
            db.flush()
            created_tasks_dict[t_name] = task
            print(f"    [+] Tarea configurada: [{task.status}] {task.name}")

        # Segundo pase: configurar predecesoras
        for item in tasks_to_create:
            if item.get("blocked_by"):
                pred_task = created_tasks_dict.get(item["blocked_by"])
                if pred_task:
                    target_task = created_tasks_dict[item["name"]]
                    target_task.blocked_by_task_id = pred_task.id
                    db.flush()
                    print(
                        f"    [->] Predecesora enlazada: '{target_task.name}' -> depende de '{pred_task.name}'"
                    )

        # 7. Configuración de Límites WIP (HU-74)
        wip_configs = [
            ("IN_PROGRESS", 2),  # Con 3 tareas, generará aviso de límite excedido
            ("CODE_REVIEW", 2),
            ("TESTING", 2),
        ]
        for col_id, limit in wip_configs:
            col_setting = (
                db.query(KanbanColumnSettingsModel)
                .filter_by(project_id=project.id, column_id=col_id)
                .first()
            )
            if col_setting is None:
                col_setting = KanbanColumnSettingsModel(
                    id=id_gen.generate(),
                    project_id=project.id,
                    column_id=col_id,
                    wip_limit=limit,
                    updated_at=now,
                )
                db.add(col_setting)
            else:
                col_setting.wip_limit = limit
                col_setting.updated_at = now
            db.flush()
            print(f"[+] Límite WIP configurado: Columna '{col_id}' = {limit}")

        # 8. Proyecto Secundario: 'Proyecto Sin Sprint Activo' (HU-72 Estado Vacío)
        empty_project = (
            db.query(ProjectModel).filter_by(name="Proyecto Demo (Sin Sprint Activo)").first()
        )
        if empty_project is None:
            empty_project = ProjectModel(
                id=id_gen.generate(),
                name="Proyecto Demo (Sin Sprint Activo)",
                description="Proyecto de prueba para validar el estado vacío del Tablero Kanban cuando no hay sprint activo",
                owner_id=manager.id,
                manager_id=manager.id,
                priority="baja",
                tech_stack='["NodeJS", "Express"]',
                status="planificacion",
                created_at=now,
                updated_at=now,
            )
            db.add(empty_project)
            db.flush()
            print(f"[+] Proyecto sin sprint creado: {empty_project.name} ({empty_project.id})")

        for u in all_users:
            m_role = "lead" if u.role in ["admin", "manager"] else "member"
            ensure_member(db, empty_project.id, u.id, m_role)

        db.commit()
        print("\n" + "=" * 70)
        print(" [EXITO] BASE DE DATOS POBLADA SATISFACTORIAMENTE PARA PRUEBAS QA")
        print("=" * 70 + "\n")
        return 0

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Falló la inserción de datos: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(seed_kanban_data())
