"""
@sad AD-09
@origin [SAD-Propuesto]
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        ...

class IdGenerator(Protocol):
    def generate(self) -> str:
        ...

class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        ...

    def verify(self, password: str, hashed: str) -> bool:
        ...

class UnitOfWork(ABC):
    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        ...

    @abstractmethod
    def commit(self) -> None:
        ...

    @abstractmethod
    def rollback(self) -> None:
        ...
