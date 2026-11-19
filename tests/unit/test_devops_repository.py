"""DevOps profile repository on SQLite."""

from sqlalchemy.orm import Session

from app.modules.devops.domain.entities import (
    EnvironmentSpec,
    PipelineStageSpec,
    ProjectDevOpsProfile,
)
from app.modules.devops.infrastructure.repositories import SqlAlchemyDevOpsProfileRepository
from app.modules.projects.infrastructure.models import ProjectModel
from tests.fakes import T0


def test_save_and_load_profile(db_session: Session) -> None:
    db_session.add(
        ProjectModel(
            id="proj-1",
            name="Demo",
            description="",
            status="planificacion",
            priority="media",
            tech_stack="[]",
            manager_id="m-1",
            owner_id="m-1",
            meeting_link=None,
            created_at=T0,
            updated_at=T0,
        )
    )
    db_session.flush()
    repo = SqlAlchemyDevOpsProfileRepository(db_session)
    profile = ProjectDevOpsProfile(
        id="prof-1",
        project_id="proj-1",
        repository_url="https://github.com/acme/app",
        ci_cd_provider="GitHub Actions",
        branching_strategy="Trunk",
        branching_rules_md=None,
        pipeline_stages=[
            PipelineStageSpec(1, "Lint", "Ruff", "ruff check .", "PR", True),
        ],
        environments=[
            EnvironmentSpec("Prod", "https://app.io", "main", "Manual", True),
        ],
        updated_by="u-1",
        created_at=T0,
        updated_at=T0,
    )
    repo.save(profile)
    db_session.commit()
    loaded = repo.get_by_project_id("proj-1")
    assert loaded is not None
    assert loaded.repository_url == profile.repository_url
    assert loaded.pipeline_stages[0].name == "Lint"
