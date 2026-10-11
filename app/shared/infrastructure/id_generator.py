"""
UUID generator implementation fulfilling the IdGenerator port.
@sad AD-09
@origin [SAD-Propuesto]
"""

import uuid

from app.shared.application.ports import IdGenerator


class UuidGenerator(IdGenerator):
    """Generates standard UUIDv4 identifiers as strings."""

    def generate(self) -> str:
        return str(uuid.uuid4())  # noqa: TID251
