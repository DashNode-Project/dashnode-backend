"""Domain validation for DevOps practices."""

import pytest

from app.modules.devops.domain.entities import (
    PipelineStageSpec,
    ProjectDevOpsProfile,
)
from app.modules.devops.domain.validation import validate_profile, validate_stage_specs
from app.shared.domain.errors import AppError


def test_duplicate_pipeline_order_raises() -> None:
    stages = [
        PipelineStageSpec(1, "A", "t", "c", "PR", True),
        PipelineStageSpec(1, "B", "t", "c", "PR", True),
    ]
    with pytest.raises(AppError) as err:
        validate_stage_specs(stages)
    assert err.value.code == "DUPLICATE_PIPELINE_ORDER"


def test_invalid_repository_url() -> None:
    profile = ProjectDevOpsProfile(
        id=None,
        project_id="p1",
        repository_url="not-a-url",
        ci_cd_provider=None,
        branching_strategy=None,
        branching_rules_md=None,
    )
    with pytest.raises(AppError) as err:
        validate_profile(profile)
    assert err.value.code == "INVALID_REPOSITORY_URL"
