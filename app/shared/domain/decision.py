"""
@sad AD-08
@origin [SAD-Propuesto]
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str | None = None

    @classmethod
    def permit(cls) -> "Decision":
        return cls(allowed=True)

    @classmethod
    def deny(cls, reason: str) -> "Decision":
        return cls(allowed=False, reason=reason)
