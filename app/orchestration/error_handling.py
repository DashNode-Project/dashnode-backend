"""
Global exception handlers implementing the single API error contract:

    {"error": {"code": "<STABLE_CODE>", "message": "<literal text>", "fields": {...}}}

Validation failures never echo the received values (they may contain passwords) and
unexpected errors never leak internals.
@sad AD-07
@origin [Archetype Convention Addition]
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.shared.domain.errors import AppError, ErrorKind

logger = logging.getLogger("dashnode.api")

TECHNICAL_FAILURE_MESSAGE = "No fue posible completar la operación. Intente nuevamente."
INVALID_REQUEST_MESSAGE = "La solicitud no es válida."

_STATUS_BY_KIND: dict[ErrorKind, int] = {
    ErrorKind.VALIDATION: status.HTTP_400_BAD_REQUEST,
    ErrorKind.UNAUTHENTICATED: status.HTTP_401_UNAUTHORIZED,
    ErrorKind.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ErrorKind.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorKind.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorKind.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
}

# Error codes after which the browser cookie is useless and must be removed.
_COOKIE_CLEARING_CODES = frozenset({"SESSION_EXPIRED", "NOT_AUTHENTICATED", "ACCOUNT_DISABLED"})


def error_body(code: str, message: str, fields: dict[str, str] | None = None) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "fields": fields or {}}}


def error_response(
    status_code: int, code: str, message: str, fields: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_body(code, message, fields))


def _app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    response = error_response(_STATUS_BY_KIND[exc.kind], exc.code, exc.message, exc.fields)
    if exc.code in _COOKIE_CLEARING_CODES:
        response.delete_cookie(
            settings.SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )
    return response


def _validation_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields: dict[str, str] = {}
    for item in exc.errors():
        location = [str(part) for part in item.get("loc", ()) if part not in ("body", "query")]
        if location:
            fields[".".join(location)] = INVALID_REQUEST_MESSAGE
    return error_response(
        status.HTTP_400_BAD_REQUEST, "INVALID_REQUEST", INVALID_REQUEST_MESSAGE, fields
    )


def _http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    message = exc.detail if isinstance(exc.detail, str) else TECHNICAL_FAILURE_MESSAGE
    response = error_response(exc.status_code, f"HTTP_{exc.status_code}", message)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # Only the exception type and route are logged: never bodies, headers or cookies.
    logger.error(
        "Unhandled error on %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc_info=True,
    )
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", TECHNICAL_FAILURE_MESSAGE
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
