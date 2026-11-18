"""Register every SQLAlchemy model on Base.metadata (schema parity / Alembic)."""


def register_all_sqlalchemy_models() -> None:
    from app.modules.ai.infrastructure import models as _ai  # noqa: F401
    from app.modules.ai_metrics.infrastructure import models as _ai_metrics  # noqa: F401
    from app.modules.auth.infrastructure import models as _auth  # noqa: F401
    from app.modules.availability.infrastructure import models as _availability  # noqa: F401
    from app.modules.backlog.infrastructure import models as _backlog  # noqa: F401
    from app.modules.documentation.infrastructure import models as _documentation  # noqa: F401
    from app.modules.fixes.infrastructure import models as _fixes  # noqa: F401
    from app.modules.kanban.infrastructure import models as _kanban  # noqa: F401
    from app.modules.notifications.infrastructure import models as _notifications  # noqa: F401
    from app.modules.projects.infrastructure import models as _projects  # noqa: F401
    from app.modules.sprints.infrastructure import models as _sprints  # noqa: F401
    from app.modules.system_knowledge.infrastructure import models as _system_knowledge  # noqa: F401
    from app.modules.tasks.infrastructure import models as _tasks  # noqa: F401
    from app.shared.infrastructure import outbox as _outbox  # noqa: F401


register_all_sqlalchemy_models()
