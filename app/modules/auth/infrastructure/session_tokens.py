"""
Opaque session token generation and digesting.

The raw token only ever travels in the HttpOnly cookie; the database stores its SHA-256
digest, so a database leak does not yield usable sessions. Tokens carry 256 bits of
entropy, so a fast unsalted hash is appropriate (unlike passwords).
@sad 5.6
@origin [Archetype Convention Addition]
"""

import hashlib
import secrets

from app.modules.auth.domain.ports import SessionTokenService

TOKEN_BYTES = 32


class SecureSessionTokenService(SessionTokenService):
    def new_token(self) -> str:
        return secrets.token_urlsafe(TOKEN_BYTES)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
