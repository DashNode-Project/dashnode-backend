"""
JWT Token service implementing TokenService port.
@sad 4.1.1, AD-09
@origin [SAD-Propuesto]
"""

from datetime import timedelta

import jwt

from app.config import settings
from app.modules.auth.domain.ports import TokenService
from app.shared.application.ports import Clock


class JwtTokenService(TokenService):
    """JWT encoding and decoding implementation."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def create_access_token(self, user_id: str, role: str, email: str, name: str = "") -> str:
        now = self._clock.now()
        exp = now + timedelta(hours=settings.SESSION_TTL_HOURS)
        payload: dict[str, object] = {
            "sub": user_id,
            "role": role,
            "email": email,
            "name": name,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        token: str = jwt.encode(
            payload,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        return token

    def decode_token(self, token: str) -> dict[str, object] | None:
        try:
            payload: dict[str, object] = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
            )
            return payload
        except jwt.PyJWTError:
            return None
