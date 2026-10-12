"""
Security and authentication orchestration.
Extracts caller identity for cross-module dependency injection.
Decoupled from specific modules to ensure BR-4 independence.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from collections.abc import Generator
from datetime import UTC, datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.database import SessionLocal

security = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """Provides a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """FastAPI dependency to authenticate the caller using the signed JWT."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta la cabecera de autorización Bearer.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload: dict[str, object] = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_value,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except jwt.PyJWTError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    user_id = str(payload.get("sub", ""))
    email = str(payload.get("email", ""))
    role = str(payload.get("role", "developer"))
    name = str(payload.get("name", ""))
    iat_val = payload.get("iat", 0)
    iat_ts = int(iat_val) if isinstance(iat_val, int | float) else 0
    created_at = datetime.fromtimestamp(iat_ts, tz=UTC)

    return CurrentUser(
        id=user_id,
        email=email,
        name=name,
        role=role,
        is_active=True,
        created_at=created_at,
    )
