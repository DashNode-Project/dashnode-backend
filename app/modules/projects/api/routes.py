"""
Projects HTTP surface is registered from app.orchestration.project_routes (BR-4).
This module keeps the package layout expected by the SAD.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/projects", tags=["projects"])
