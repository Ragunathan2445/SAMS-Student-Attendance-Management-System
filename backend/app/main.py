
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import auth, files, parent, public, teacher, teacher_salary, teacher_students, teacher_substitute
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.db import mongo
from app.db.session import engine
from app.middleware.security import CSRFHeaderMiddleware, SecurityHeadersMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    mongo.ensure_indexes()
    mongo.log_system_event("startup", "Backend started")
    yield
    mongo.log_system_event("shutdown", "Backend stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="School Attendance Management System API",
        version="1.0.0",
        description="Parent & Teacher portals – localhost demonstration build.",
        lifespan=lifespan,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFHeaderMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With"],
    )
    register_exception_handlers(app)

    for router in (public.router, auth.router, parent.router, teacher.router, teacher_substitute.router,
                   teacher_students.router, teacher_salary.router, files.router):
        app.include_router(router, prefix="/api")

    @app.get("/api/health", tags=["Public"])
    def health():
        db_ok = mongo_ok = False
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:  # pragma: no cover
            pass
        try:
            mongo.get_mongo_db().command("ping")
            mongo_ok = True
        except Exception:  # pragma: no cover
            pass
        return {"status": "ok" if db_ok else "degraded", "postgresql": db_ok, "mongodb": mongo_ok}

    return app


app = create_app()
