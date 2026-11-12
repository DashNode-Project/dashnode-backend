"""
HTTP hardening middleware: security headers and cookie-session CSRF defence.

CSRF strategy (cookie sessions): SameSite cookie + strict Origin allow-list check on
state-changing methods. Requests without an Origin header (non-browser clients) cannot
ride a victim's cookie and are not affected.
@sad AD-07
@origin [Archetype Convention Addition]
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.orchestration.error_handling import TECHNICAL_FAILURE_MESSAGE, error_response

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            # Authenticated responses must never be stored by browsers or proxies.
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is not None and origin not in settings.cors_origins_list:
                return error_response(403, "ORIGIN_NOT_ALLOWED", TECHNICAL_FAILURE_MESSAGE)
        return await call_next(request)
