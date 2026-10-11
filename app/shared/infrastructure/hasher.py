"""
Argon2 password hasher implementation fulfilling the PasswordHasher port.
@sad AD-09
@origin [SAD-Propuesto]
"""

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import VerificationError

from app.shared.application.ports import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Argon2id password hashing adapter."""

    def __init__(self) -> None:
        self._ph = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return self._ph.verify(hashed, password)
        except VerificationError:
            return False
