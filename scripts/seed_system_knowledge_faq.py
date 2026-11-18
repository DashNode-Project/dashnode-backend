"""Idempotent seed: 30+ DashNode manual FAQ entries for the system knowledge base."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select

from app.config import settings
from app.modules.auth.infrastructure.models import UserModel
from app.modules.system_knowledge.infrastructure.models import SystemKnowledgeEntryModel
from app.shared.infrastructure import database as db_runtime
from app.shared.infrastructure.database import initialize_database
from app.shared.infrastructure.id_generator import UuidGenerator

FAQ: list[tuple[str, str, str]] = [
    (
        "¿Cómo inicio sesión en DashNode?",
        "Use su correo y contraseña en la pantalla de inicio. Tras **5 intentos fallidos** "
        "en 15 minutos la cuenta se bloquea temporalmente.",
        "auth,login",
    ),
    (
        "¿Qué roles existen?",
        "Hay **Administrador**, **Gerente** y **Desarrollador**. El registro público solo crea Gerentes.",
        "rbac,roles",
    ),
    (
        "¿Cómo creo un proyecto?",
        "Como Gerente o Admin: menú **Proyectos** → **Nuevo proyecto**, complete nombre, "
        "descripción y prioridad.",
        "proyectos",
    ),
    (
        "¿Dónde veo el resumen del proyecto?",
        "Dentro del proyecto, pestaña **Resumen**: progreso, velocidad, issues y equipo.",
        "resumen",
    ),
    (
        "¿Cómo gestiono el equipo del proyecto?",
        "Pestaña **Equipo**: agregar o retirar integrantes (no en Resumen).",
        "equipo",
    ),
    (
        "¿Qué son las épicas?",
        "Agrupan historias de usuario en el backlog por área funcional.",
        "backlog,epicas",
    ),
    (
        "¿Qué es DoR y DoD en una HU?",
        "**Definition of Ready** y **Definition of Done** son criterios en Markdown en el detalle de la HU.",
        "hu,dor,dod",
    ),
    (
        "¿Cómo planifico un sprint?",
        "Pestaña **Sprints**: crear sprint, asignar HUs y activar el sprint.",
        "sprints",
    ),
    (
        "¿Cómo reporto un fix?",
        "Pestaña **Issues**: crear issue, adjuntar evidencias y usar análisis IA si aplica.",
        "issues,fixes",
    ),
    (
        "¿Dónde están mis tareas?",
        "Menú **Mis tareas**: filtre por proyecto y cambie entre lista, tabla y kanban.",
        "tareas",
    ),
    (
        "¿Cómo funciona el kanban?",
        "Por proyecto, pestaña **Kanban**: columnas WIP con drag and drop de tarjetas.",
        "kanban",
    ),
    (
        "¿Cómo documento el proyecto?",
        "Pestaña **Documentación**: entradas Markdown con categoría y visibilidad.",
        "documentacion",
    ),
    (
        "¿Cómo agendo reuniones?",
        "Pestaña **Reuniones** o **Disponibilidad**: buscar huecos y convocar participantes.",
        "reuniones",
    ),
    (
        "¿Qué hace el asistente IA?",
        "Responde con datos del proyecto (HUs, sprints, docs) y el manual del sistema.",
        "ia,asistente",
    ),
    (
        "¿Dónde veo métricas de IA?",
        "En el proyecto, pestaña **Métricas IA** (Gerente/Admin).",
        "metricas-ia",
    ),
    (
        "¿Puedo valorar una respuesta de IA?",
        "Sí, use el control de valoración en el widget del asistente o en análisis de issues.",
        "ia,valoracion",
    ),
    (
        "¿Cómo cambio mi contraseña?",
        "Perfil → seguridad (si está habilitado) o solicite recuperación por correo.",
        "perfil,auth",
    ),
    (
        "¿Cómo invito a un desarrollador?",
        "El Gerente agrega miembros en **Equipo** desde usuarios activos del sistema.",
        "equipo,invitaciones",
    ),
    (
        "¿Qué significa el estado Corrección en una tarea?",
        "Indica que hay un fix abierto; el estado solo cambia al resolver el issue.",
        "tareas,fixes",
    ),
    (
        "¿Cómo registro tiempo en una tarea?",
        "En el detalle de tarea dentro del backlog, registro de horas y comentario.",
        "tiempo",
    ),
    (
        "¿Quién aprueba documentación?",
        "Gerente del proyecto según flujo EP-09; desarrolladores ven entradas aprobadas.",
        "documentacion,aprobacion",
    ),
    (
        "¿Cómo uso atajos de teclado?",
        "Ícono de teclado en la barra superior o manual de usuario.",
        "ux,atajos",
    ),
    (
        "¿La sesión expira?",
        "Sí, por defecto **8 horas**; el mensaje indicará que debe iniciar sesión de nuevo.",
        "sesion,seguridad",
    ),
    (
        "¿Puedo exportar métricas de IA?",
        "En EP-13 v1 el panel es consulta en UI; exportación completa puede estar pendiente.",
        "metricas-ia",
    ),
    (
        "¿Cómo funcionan las notificaciones?",
        "Campana en cabecera: eventos de proyecto, fixes y aprobaciones.",
        "notificaciones",
    ),
    (
        "¿Qué es la velocidad en resumen?",
        "Promedio de puntos completados en los últimos sprints cerrados.",
        "resumen,metricas",
    ),
    (
        "¿Cómo asigno puntos a una HU?",
        "Modo historia o suma de puntos por tareas según **modo de estimación**.",
        "estimacion",
    ),
    (
        "¿Puedo mover HUs entre épicas?",
        "Sí en backlog con permisos de estructura (Gerente).",
        "backlog",
    ),
    (
        "¿Cómo consulto issues con el asistente?",
        "Pregunte por issues del proyecto; respeta permisos de membresía.",
        "ia,issues",
    ),
    (
        "¿Dónde está la base de conocimientos?",
        "Manual del sistema vía API `/knowledge/system` y respuestas del asistente.",
        "knowledge,manual",
    ),
    (
        "¿Qué proveedor de base de datos usa DashNode?",
        "PostgreSQL principal (p. ej. Supabase) con fallback local opcional documentado en health.",
        "infra,db",
    ),
]


def _author(db) -> UserModel:
    email = settings.SEED_ADMIN_EMAIL or settings.SEED_MANAGER_EMAIL
    user = db.query(UserModel).filter_by(email=email).first()
    if user is None:
        raise RuntimeError("Seed admin/manager user required for knowledge author")
    return user


def main() -> None:
    initialize_database()
    gen = UuidGenerator()
    now = datetime.now(UTC)
    if db_runtime.SessionLocal is None:
        raise RuntimeError("SessionLocal not initialized")
    with db_runtime.SessionLocal() as db:
        author = _author(db)
        created = 0
        for question, answer, tags in FAQ:
            exists = db.scalar(
                select(SystemKnowledgeEntryModel.id).where(
                    SystemKnowledgeEntryModel.question == question,
                    SystemKnowledgeEntryModel.is_deleted.is_(False),
                )
            )
            if exists:
                continue
            db.add(
                SystemKnowledgeEntryModel(
                    id=gen.generate(),
                    question=question,
                    answer_md=answer,
                    tags=tags,
                    author_id=author.id,
                    is_published=True,
                    is_deleted=False,
                    created_at=now,
                    updated_at=now,
                )
            )
            created += 1
        db.commit()
        print(f"[seed] system knowledge: {created} new entries ({len(FAQ)} defined)")


if __name__ == "__main__":
    main()
