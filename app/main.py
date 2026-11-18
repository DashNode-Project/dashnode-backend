"""
@sad AD-07
@origin [Archetype Convention Addition]
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth.api.routes import router as auth_router
from app.orchestration.notification_routes import router as notifications_router
from app.modules.tasks.api.routes import router as tasks_router
from app.orchestration.ai_metrics_routes import router as ai_metrics_router
from app.orchestration.ai_routes import router as ai_router
from app.orchestration.auth_container import build_session_authenticator
from app.orchestration.availability_routes import router as availability_router
from app.orchestration.backlog_routes import router as backlog_router
from app.orchestration.documentation_routes import router as documentation_router
from app.orchestration.error_handling import register_error_handlers
from app.orchestration.issue_routes import router as issue_router
from app.orchestration.kanban_routes import router as kanban_router
from app.orchestration.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware
from app.orchestration.profile_routes import router as profile_router
from app.orchestration.project_routes import router as projects_router
from app.orchestration.security import register_session_authenticator
from app.orchestration.sprint_routes import router as sprint_router
from app.orchestration.system_knowledge_routes import router as system_knowledge_router
from app.orchestration.user_administration_routes import router as user_administration_router
from app.shared.infrastructure.database import (
    get_database_provider_status,
    get_db_session,
    initialize_database,
)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(
    title="DashNode API",
    description="Backend API para DashNode",
    version="1.0.0",
    lifespan=_lifespan,
    docs_url=None if settings.APP_ENV == "production" else "/docs",
    redoc_url=None if settings.APP_ENV == "production" else "/redoc",
    openapi_url=None if settings.APP_ENV == "production" else "/openapi.json",
)

register_error_handlers(app)
register_session_authenticator(build_session_authenticator)

# Added last = outermost: headers wrap everything, then CORS, then the CSRF origin check.
app.add_middleware(OriginCheckMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Idempotency-Key"],
)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(user_administration_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(availability_router, prefix="/api/v1")
app.include_router(backlog_router, prefix="/api/v1")
app.include_router(sprint_router, prefix="/api/v1")
app.include_router(kanban_router, prefix="/api/v1")
app.include_router(documentation_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(ai_metrics_router, prefix="/api/v1")
app.include_router(issue_router, prefix="/api/v1")
app.include_router(system_knowledge_router, prefix="/api/v1")


@app.get("/health", tags=["public"])
def health_check() -> dict[str, str]:
    """Liveness probe: the process is up. Public and free of side effects."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["public"], response_model=None)
def readiness_check(db: Session = Depends(get_db_session)) -> JSONResponse | dict[str, object]:
    """Readiness probe: the database answers."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    provider = get_database_provider_status()
    payload: dict[str, object] = {"status": "ready"}
    if provider is not None:
        payload["database_provider"] = provider.role.value
        payload["database_url_label"] = provider.url_label
        if provider.limitations:
            payload["database_limitations"] = provider.limitations
    return payload
