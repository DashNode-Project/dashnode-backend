"""
Argon2 password hasher implementation fulfilling the PasswordHasher port.
@sad AD-09
@origin [SAD-Propuesto]
"""

import secrets

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings
from app.shared.application.ports import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Argon2id password hashing adapter (salted, parameters from configuration)."""

    def __init__(
        self,
        time_cost: int | None = None,
        memory_cost_kib: int | None = None,
        parallelism: int | None = None,
    ) -> None:
        self._ph = Argon2Hasher(
            time_cost=time_cost or settings.ARGON2_TIME_COST,
            memory_cost=memory_cost_kib or settings.ARGON2_MEMORY_COST_KIB,
            parallelism=parallelism or settings.ARGON2_PARALLELISM,
        )
        self._dummy_hash: str | None = None

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return self._ph.verify(hashed, password)
        except (VerificationError, InvalidHashError):
            return False

    def verify_dummy(self, password: str) -> None:
        """Spend the same time as a real verification (anti user-enumeration timing)."""
        if self._dummy_hash is None:
            self._dummy_hash = self._ph.hash(secrets.token_urlsafe(16))
        self.verify(password, self._dummy_hash)
