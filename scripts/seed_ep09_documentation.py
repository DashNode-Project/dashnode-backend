"""Poblador de datos de prueba para la Épica 09 (Documentación y Base de Conocimiento).

Crea usuarios, proyecto demo y entradas de documentación (ancladas y no ancladas)
para verificar manualmente las historias de usuario HU_DN_06_87 y HU_DN_06_89 en el frontend.
"""

import os
import socket
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

# Agregar directorio backend al sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Configurar DATABASE_URL antes de importar módulos que cargan app.config.settings
env_file = backend_dir / ".env"
db_url = os.environ.get("DATABASE_URL")
if not db_url and env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                db_url = line.split("=", 1)[1].strip()
                break

is_postgres_alive = False
if db_url and "psycopg" in db_url and "--sqlite" not in sys.argv:
    try:
        s = socket.create_connection(("127.0.0.1", 5434), timeout=1)
        s.close()
        is_postgres_alive = True
    except Exception:
        is_postgres_alive = False

sqlite_path = backend_dir / "data" / "dashnode.db"
sqlite_path.parent.mkdir(parents=True, exist_ok=True)
sqlite_url = f"sqlite+pysqlite:///{sqlite_path.resolve()}"

active_db_url: str
if is_postgres_alive and "--sqlite" not in sys.argv:
    if db_url is None:
        print("[ERROR] DATABASE_URL no configurada; use --sqlite o defina .env")
        sys.exit(1)
    active_db_url = db_url
    db_desc = "PostgreSQL (Docker / Local en puerto 5434)"
else:
    active_db_url = sqlite_url
    db_desc = f"SQLite local ({sqlite_path.resolve()})"

os.environ["DATABASE_URL"] = active_db_url

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.infrastructure.models import UserModel
from app.modules.documentation.domain.entities import (
    DocumentationApprovalStatus,
    DocumentationCategory,
)
from app.modules.documentation.infrastructure.models import DocumentationEntryModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.hasher import Argon2PasswordHasher
from app.shared.infrastructure.id_generator import UuidGenerator

id_gen = UuidGenerator()
hasher = Argon2PasswordHasher()
now = datetime.now(UTC)

SEPARATOR = "=" * 80
SUB_SEPARATOR = "-" * 80


class DocSeedItem(TypedDict):
    title: str
    category: str
    objective: str
    tags: str
    content: str | None
    external_url: str | None
    approval_status: str
    is_pinned: bool
    is_visible_to_devs: bool
    author_id: str
    created_at: datetime


def get_engine_and_session() -> tuple[Engine, sessionmaker[Session], str]:
    """Obtiene el motor y fábrica de sesiones según active_db_url."""
    connect_args = {"check_same_thread": False} if "sqlite" in active_db_url else {}
    engine = create_engine(active_db_url, connect_args=connect_args)
    return engine, sessionmaker(bind=engine), db_desc


def get_or_create_user(
    db: Session, email: str, role: str, name: str, password_plain: str
) -> UserModel:
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
        print(f"  [+] Creado usuario: {name} ({email}) - Rol: {role}")
    else:
        user.is_active = True
        user.name = name
        user.role = role
        user.hashed_password = hasher.hash(password_plain)
        db.flush()
        print(f"  [=] Actualizado usuario: {name} ({email}) - Rol: {role}")
    return user


def ensure_member(db: Session, project_id: str, user_id: str, role: str = "member") -> None:
    member = db.query(ProjectMemberModel).filter_by(project_id=project_id, user_id=user_id).first()
    if member is None:
        db.add(ProjectMemberModel(project_id=project_id, user_id=user_id, role=role, joined_at=now))
        db.flush()


def seed_demo_data() -> None:
    print("\n" + SEPARATOR)
    print("  DASHNODE - POBLADOR DE DATOS DE PRUEBA PARA ÉPICA 09 (DOCUMENTACIÓN)")
    print("  Historias de Usuario: HU_DN_06_87 y HU_DN_06_89 (Anclaje y Gestión de Destacados)")
    print(SEPARATOR)

    engine, session_factory, db_desc = get_engine_and_session()
    print(f"\n[BD] Base de datos activa: {db_desc}")

    # Asegurar tablas creadas
    Base.metadata.create_all(bind=engine)

    with session_factory() as db:
        # 1. Crear usuarios de prueba con contraseñas sencillas para el frontend
        print("\n1. Configurando Usuarios de Prueba:")
        admin_pwd = "Admin123*"
        manager_pwd = "Manager123*"
        dev_pwd = "Dev1234*"

        admin = get_or_create_user(
            db, "admin@dashnode.local", "admin", "Administrador DashNode", admin_pwd
        )
        manager = get_or_create_user(
            db, "manager@dashnode.local", "manager", "Gerente Carlos Mendoza", manager_pwd
        )
        dev = get_or_create_user(
            db, "developer@dashnode.local", "developer", "Desarrollador Juan Pérez", dev_pwd
        )

        # 2. Crear o reutilizar Proyecto Demo
        print("\n2. Configurando Proyecto de Base de Conocimiento:")
        project_name = "Proyecto Base de Conocimiento EP-09"
        project = db.query(ProjectModel).filter(ProjectModel.name == project_name).first()
        if project is None:
            project = ProjectModel(
                id=id_gen.generate(),
                name=project_name,
                description="Proyecto de prueba para validar anclaje, visibilidad y catálogo de documentación",
                owner_id=manager.id,
                manager_id=manager.id,
                priority="alta",
                tech_stack='["React 19", "FastAPI", "TailwindCSS"]',
                status="activo",
                created_at=now,
                updated_at=now,
            )
            db.add(project)
            db.flush()
            print(f"  [+] Creado proyecto: '{project.name}' (ID: {project.id})")
        else:
            print(f"  [=] Reutilizando proyecto existente: '{project.name}' (ID: {project.id})")

        # Asegurar membresía de todos los usuarios en el proyecto
        ensure_member(db, project.id, admin.id, role="admin")
        ensure_member(db, project.id, manager.id, role="manager")
        ensure_member(db, project.id, dev.id, role="member")
        print("  [+] Membresías vinculadas (Admin, Gerente y Desarrollador)")

        # 3. Limpiar entradas anteriores de este proyecto para un inicio determinista
        deleted_count = (
            db.query(DocumentationEntryModel)
            .filter(DocumentationEntryModel.project_id == project.id)
            .delete()
        )
        if deleted_count > 0:
            print(f"  [i] Se limpiaron {deleted_count} entradas anteriores del proyecto demo.")

        # 4. Crear entradas realistas de prueba para HU 87 y 89
        print("\n3. Creando Entradas de Documentación para Pruebas Manuales:")

        entries_data: list[DocSeedItem] = [
            {
                "title": "⭐ [ANCLADA] Estándares de Arquitectura Hexagonal y Convenciones de Código",
                "category": DocumentationCategory.TECNICA.value,
                "objective": "Guía maestra del equipo con las directrices de diseño, patrones de puertos y adaptadores y reglas CI/CD.",
                "tags": "arquitectura, hexagonal, backend, python",
                "content": "Esta guía define la arquitectura del sistema DashNode. Todo acceso a datos debe realizarse a través de repositorios inyectados en los casos de uso. Las entidades del dominio no deben importar FastAPI ni SQLAlchemy (BR-2).",
                "external_url": None,
                "approval_status": DocumentationApprovalStatus.APPROVED.value,
                "is_pinned": True,  # Ya anclada para probar HU_DN_06_87 (Desanclar)
                "is_visible_to_devs": True,
                "author_id": manager.id,
                "created_at": now - timedelta(days=5),
            },
            {
                "title": "📋 Guía de Onboarding para Nuevos Desarrolladores",
                "category": DocumentationCategory.GENERAL.value,
                "objective": "Instrucciones de bienvenida e instalación para incorporar desarrolladores al proyecto.",
                "tags": "onboarding, setup, frontend, backend",
                "content": "Paso 1: Clonar el repositorio. Paso 2: Ejecutar 'npm install' en dashnode-frontend. Paso 3: Configurar variables de entorno y ejecutar 'npm run dev'.",
                "external_url": None,
                "approval_status": DocumentationApprovalStatus.APPROVED.value,
                "is_pinned": False,  # No anclada para probar HU_DN_06_87 / HU_DN_06_89 (Anclar)
                "is_visible_to_devs": True,
                "author_id": dev.id,
                "created_at": now - timedelta(days=4),
            },
            {
                "title": "🔒 Políticas de Seguridad y Autenticación con Cookies HttpOnly",
                "category": DocumentationCategory.TECNICA.value,
                "objective": "Explicación del esquema de sesiones en servidor y prevención de fugas de tokens.",
                "tags": "seguridad, owasp, sesiones, auth",
                "content": "Las credenciales y tokens nunca se exponen al almacenamiento web del navegador (localStorage/sessionStorage). Se utiliza una cookie HttpOnly 'dashnode_session' con SameSite Lax y cifrado Argon2id para las contraseñas.",
                "external_url": None,
                "approval_status": DocumentationApprovalStatus.APPROVED.value,
                "is_pinned": False,  # No anclada
                "is_visible_to_devs": True,
                "author_id": admin.id,
                "created_at": now - timedelta(days=3),
            },
            {
                "title": "📅 Minuta de Sprint Planning y Definición de Metas",
                "category": DocumentationCategory.REUNION.value,
                "objective": "Registro de acuerdos y asignaciones de la sesión de inicio de sprint.",
                "tags": "reunión, sprint, planificación, scrum",
                "content": "El equipo acordó completar las historias de usuario de la Épica 9 (Documentación) priorizando el mecanismo de fijado/anclado y la visibilidad de recursos para el equipo técnico.",
                "external_url": None,
                "approval_status": DocumentationApprovalStatus.APPROVED.value,
                "is_pinned": False,  # No anclada
                "is_visible_to_devs": True,
                "author_id": manager.id,
                "created_at": now - timedelta(days=2),
            },
            {
                "title": "🌐 Documentación Oficial de React 19 y TailwindCSS v4",
                "category": DocumentationCategory.FUNCIONAL.value,
                "objective": "Referencias externas recomendadas para el desarrollo de componentes en el frontend.",
                "tags": "react, tailwindcss, ui, enlace-externo",
                "content": "Consultar la documentación oficial para conocer los nuevos hooks de React 19 y las clases optimizadas de TailwindCSS.",
                "external_url": "https://react.dev",
                "approval_status": DocumentationApprovalStatus.APPROVED.value,
                "is_pinned": False,  # No anclada
                "is_visible_to_devs": True,
                "author_id": dev.id,
                "created_at": now - timedelta(days=1),
            },
        ]

        for item in entries_data:
            entry = DocumentationEntryModel(
                id=id_gen.generate(),
                project_id=project.id,
                author_id=item["author_id"],
                title=item["title"],
                category=item["category"],
                objective=item["objective"],
                tags=item["tags"],
                content=item["content"],
                external_url=item["external_url"],
                approval_status=item["approval_status"],
                is_pinned=item["is_pinned"],
                is_visible_to_devs=item["is_visible_to_devs"],
                rejection_reason=None,
                is_deleted=False,
                created_at=item["created_at"],
                updated_at=item["created_at"],
            )
            db.add(entry)
            pin_badge = "📌 [ANCLADA]" if item["is_pinned"] else "📄 [Normal]"
            print(f"  {pin_badge} '{item['title'][:55]}...' ({item['category']})")

        db.commit()

        print("\n" + SEPARATOR)
        print("  DATOS POBLADOS SATISFACTORIAMENTE PARA PRUEBAS MANUALES")
        print(SEPARATOR)
        print(f"  Proyecto ID: {project.id}")
        print(f"  Ruta directa en frontend: /proyectos/{project.id}/conocimiento")
        print(SUB_SEPARATOR)
        print("  CUENTAS DE ACCESO:")
        print(f"  1. Gerente:       manager@dashnode.local   | Password: {manager_pwd}")
        print(f"  2. Administrador: admin@dashnode.local     | Password: {admin_pwd}")
        print(f"  3. Desarrollador: developer@dashnode.local | Password: {dev_pwd}")
        print(SEPARATOR + "\n")


if __name__ == "__main__":
    seed_demo_data()
