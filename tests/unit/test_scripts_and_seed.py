"""
Tests for the developer tooling: secret scanner, .env generator and the seed command.
@sad AD-09
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.cli import seed as seed_module
from app.config import settings
from app.modules.auth.infrastructure.models import UserModel
from app.shared.infrastructure.hasher import Argon2PasswordHasher

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scan = _load("scan_secrets")
gen = _load("generate_env")


# --- scan_secrets -----------------------------------------------------------------


def test_scanner_detects_strong_secrets_without_echoing_them() -> None:
    aws_key = "AKIA" + "A" * 16
    pem = "-----BEGIN " + "PRIVATE KEY-----"
    findings = scan.scan_text("app/x.py", f"a = 1\nkey = '{aws_key}'\n{pem}\n")
    assert any(":2: AWS access key id" in item for item in findings)
    assert any(":3: private key block" in item for item in findings)
    assert all(aws_key not in item for item in findings)


def test_scanner_flags_hardcoded_assignments_and_url_credentials() -> None:
    value = "".join(["Zq", "9xLm", "Pw3Rt"])
    assert scan.scan_text("app/x.py", f'api_key = "{value}"')
    assert scan.scan_text("app/x.py", f'DB = "postgresql://user:{value}@host/db"')


def test_scanner_accepts_placeholders_and_env_lookups() -> None:
    clean = [
        'password = "CHANGE_ME_DB_PASSWORD"',
        'token = os.environ["API_TOKEN_VALUE"]',
        'DB = "postgresql://user:${DB_PASSWORD}@host/db"',
        'secret = "<set me>"',
    ]
    for line in clean:
        assert scan.scan_text("app/x.py", line) == []


def test_scanner_relaxes_assignment_rule_only_for_tests() -> None:
    value = "".join(["Zq", "9xLm", "Pw3Rt"])
    assert scan.scan_text("tests/test_x.py", f'password = "{value}"') == []
    assert scan.scan_text("tests/test_x.py", f'DB = "postgresql://user:{value}@host/db"')


@pytest.mark.parametrize("path", [".env", ".env.local", "keys/server.pem", "a/b/id.key"])
def test_scanner_rejects_sensitive_file_types(path: str) -> None:
    assert scan.scan_paths([path], reader=lambda _p: "")


def test_scanner_allows_env_example() -> None:
    assert scan.scan_paths([".env.example"], reader=lambda _p: "A=1") == []


# --- generate_env -----------------------------------------------------------------


def test_generate_env_replaces_every_placeholder_with_distinct_random_values() -> None:
    content, generated = gen.build_env()
    assert not re.search(r"^[A-Z_]+=.*CHANGE_ME", content, re.MULTILINE)
    assert len(generated) == 5
    db_passwords = set(re.findall(r"^POSTGRES_PASSWORD=(.+)$", content, re.MULTILINE))
    assert len(db_passwords) == 1
    db_password = db_passwords.pop()
    assert f":{db_password}@" in content  # same value embedded in DATABASE_URL
    seeds = re.findall(r"^SEED_\w+_PASSWORD=(.+)$", content, re.MULTILINE)
    assert len(set(seeds)) == 4
    for password in seeds:
        assert 8 <= len(password) <= 64
        assert re.search(r"[A-Za-z]", password)
        assert re.search(r"\d", password)
    other, _ = gen.build_env()
    assert other != content  # fresh randomness on every run


# --- seed -------------------------------------------------------------------------


@pytest.fixture
def seed_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "SEED_ADMIN_EMAIL": "admin@example.test",
        "SEED_ADMIN_PASSWORD": SecretStr("Admin1234"),
        "SEED_MANAGER_EMAIL": "mgr@example.test",
        "SEED_MANAGER_PASSWORD": SecretStr("Mgr123456"),
        "SEED_DEVELOPER_EMAIL": "dev@example.test",
        "SEED_DEVELOPER_PASSWORD": SecretStr("Devel1234"),
        "SEED_DISABLED_EMAIL": "off@example.test",
        "SEED_DISABLED_PASSWORD": SecretStr("Off123456"),
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)


@pytest.mark.usefixtures("seed_settings")
def test_seed_creates_users_hashes_passwords_and_is_idempotent(db_session: Session) -> None:
    assert seed_module.seed(db_session) == 0
    assert seed_module.seed(db_session) == 0

    users = {user.email: user for user in db_session.query(UserModel).all()}
    assert set(users) == {
        "admin@example.test",
        "mgr@example.test",
        "dev@example.test",
        "off@example.test",
    }
    assert users["off@example.test"].is_active is False
    assert users["admin@example.test"].role == "admin"
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
    assert hasher.verify("Admin1234", users["admin@example.test"].hashed_password)
    assert "Admin1234" not in users["admin@example.test"].hashed_password


def test_seed_refuses_when_not_configured(db_session: Session) -> None:
    assert seed_module.seed(db_session) == 1
    assert db_session.query(UserModel).count() == 0


@pytest.mark.usefixtures("seed_settings")
def test_seed_is_blocked_in_production(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert seed_module.seed(db_session) == 1
    assert db_session.query(UserModel).count() == 0
