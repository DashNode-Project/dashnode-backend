"""DevOps repository defaults on SQLite."""

from app.modules.ai.infrastructure.models import SystemConfigModel
from app.modules.devops.infrastructure.repositories import SqlAlchemyDevopsPipelineRepository


def test_load_sim_config_reads_system_rows(db_session) -> None:
    db_session.add(SystemConfigModel(key="devops_sim_duration_lint_s", value="20"))
    db_session.commit()
    repo = SqlAlchemyDevopsPipelineRepository(db_session)
    cfg = repo.load_sim_config()
    assert cfg.duration_lint_s == 20


def test_cooldown_default_when_config_missing(db_session) -> None:
    repo = SqlAlchemyDevopsPipelineRepository(db_session)
    assert repo.cooldown_seconds() == 300


def test_load_sim_config_applies_all_keys(db_session) -> None:
    rows = {
        "devops_sim_success_lint": "0.5",
        "devops_sim_success_test": "0.6",
        "devops_sim_success_build": "0.7",
        "devops_sim_success_deploy": "0.8",
        "devops_sim_duration_lint_s": "11",
        "devops_sim_duration_test_s": "22",
        "devops_sim_duration_build_s": "33",
        "devops_sim_duration_deploy_s": "44",
    }
    for key, value in rows.items():
        db_session.add(SystemConfigModel(key=key, value=value))
    db_session.commit()
    cfg = SqlAlchemyDevopsPipelineRepository(db_session).load_sim_config()
    assert cfg.success_lint == 0.5
    assert cfg.duration_deploy_s == 44


def test_get_latest_returns_none_when_empty(db_session) -> None:
    repo = SqlAlchemyDevopsPipelineRepository(db_session)
    assert repo.get_latest("missing-project") is None