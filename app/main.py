"""
@sad AD-07
@origin [Archetype Convention Addition]
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth.api.routes import router as auth_router
from app.modules.notifications.api.routes import router as notifications_router
from app.modules.projects.api.routes import router as projects_router
from app.modules.tasks.api.routes import router as tasks_router
from app.orchestration.auth_container import build_session_authenticator
from app.orchestration.error_handling import register_error_handlers
from app.orchestration.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware
from app.orchestration.profile_routes import router as profile_router
from app.orchestration.security import register_session_authenticator
from app.orchestration.user_administration_routes import router as user_administration_router
from app.shared.infrastructure.database import get_db_session

app = FastAPI(
    title="DashNode API",
    description="Backend API para DashNode",
    version="1.0.0",
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
    allow_headers=["Content-Type", "Accept"],
)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(user_administration_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")


@app.get("/health", tags=["public"])
def health_check() -> dict[str, str]:
    """Liveness probe: the process is up. Public and free of side effects."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["public"], response_model=None)
def readiness_check(db: Session = Depends(get_db_session)) -> JSONResponse | dict[str, str]:
    """Readiness probe: the database answers."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}
