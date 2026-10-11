"""
Unit tests for shared infrastructure adapters.
@sad AD-09
"""

import uuid
from datetime import UTC

from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.hasher import Argon2PasswordHasher
from app.shared.infrastructure.id_generator import UuidGenerator


def test_system_clock_returns_utc() -> None:
    clock = SystemClock()
    t = clock.now()
    assert t.tzinfo is not None
    assert t.tzinfo == UTC


def test_uuid_generator_generates_valid_uuid() -> None:
    generator = UuidGenerator()
    val = generator.generate()
    parsed = uuid.UUID(val)
    assert parsed.version == 4


def test_argon2_password_hasher() -> None:
    hasher = Argon2PasswordHasher()
    secret = "my_secure_password_123"
    hashed = hasher.hash(secret)
    assert hashed != secret
    assert hasher.verify(secret, hashed) is True
    assert hasher.verify("wrong_password", hashed) is False
