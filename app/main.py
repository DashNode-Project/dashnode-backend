"""
@sad AD-07
@origin [Archetype Convention Addition]
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.modules.auth.api.routes import router as auth_router
from app.modules.notifications.api.routes import router as notifications_router
from app.modules.projects.api.routes import router as projects_router
from app.modules.tasks.api.routes import router as tasks_router

app = FastAPI(
    title="DashNode API",
    description="Backend API para DashNode",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")


@app.get("/health", tags=["public"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
