"""HTTP middleware: CSRF header check for state-changing requests and security headers."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "SAMS"


class CSRFHeaderMiddleware(BaseHTTPMiddleware):
    """Session cookies are SameSite=Lax + HttpOnly. In addition every unsafe API request
    must carry a custom header, which browsers will not send cross-origin without a CORS
    pre-flight that our CORS policy only grants to the configured frontend origins."""

    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS and request.url.path.startswith("/api/"):
            if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
                return JSONResponse(status_code=403, content={"detail": "Missing or invalid request header.", "code": "csrf"})
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response
