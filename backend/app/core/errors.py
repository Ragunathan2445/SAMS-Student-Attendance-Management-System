"""Domain exceptions mapped to clean HTTP responses (no internal details leaked)."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("sams.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class TooManyRequests(AppError):
    status_code = 429
    code = "rate_limited"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path"))
            errors.append({"field": loc, "message": err.get("msg", "Invalid value")})
        first = errors[0]["message"] if errors else "Invalid request"
        return JSONResponse(
            status_code=422, content={"detail": f"Validation failed: {first}", "code": "validation_error", "errors": errors}
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        logger.warning("Integrity error: %s", exc.orig.__class__.__name__ if exc.orig else exc)
        return JSONResponse(
            status_code=409,
            content={"detail": "This change conflicts with an existing record.", "code": "conflict"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred.", "code": "server_error"})
