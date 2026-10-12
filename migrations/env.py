from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings

# Import all models to register on Base.metadata
from app.modules.auth.infrastructure.models import (  # noqa: F401
    LoginAttemptModel,
    SessionModel,
    UserModel,
)
from app.modules.notifications.infrastructure.models import (  # noqa: F401
    NotificationModel,
)
from app.modules.projects.infrastructure.models import (  # noqa: F401
    ProjectMemberModel,
    ProjectModel,
)
from app.modules.tasks.infrastructure.models import TaskModel  # noqa: F401
from app.shared.infrastructure.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    """Explicit override (tests, tooling) wins; otherwise the configured DATABASE_URL."""
    return config.get_main_option("sqlalchemy.url") or settings.DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
