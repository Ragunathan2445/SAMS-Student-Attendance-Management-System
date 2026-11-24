"""Audit logging: PostgreSQL ``audit_logs`` (authoritative, same transaction) plus a
best-effort MongoDB ``activity_logs`` entry for the activity feed."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db import mongo
from app.models import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def record(
    db: Session,
    *,
    account_id: int | None,
    role: str | None,
    action: str,
    entity_type: str | None = None,
    entity_id: Any = None,
    details: dict | None = None,
    ip: str | None = None,
) -> None:
    """Add an audit row to the current transaction (caller commits)."""
    db.add(
        AuditLog(
            account_id=account_id,
            role=role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=_jsonable(details or {}),
            ip_address=ip,
        )
    )


def activity(
    *, account_id: int | None, role: str | None, activity_type: str, description: str,
    entity_type: str | None = None, entity_id: Any = None, metadata: dict | None = None,
) -> None:
    """Supplementary activity feed entry in MongoDB (call after a successful commit)."""
    mongo.log_activity(
        user_id=account_id,
        user_role=role,
        activity_type=activity_type,
        description=description,
        record_ref={"type": entity_type, "id": str(entity_id) if entity_id is not None else None},
        metadata=_jsonable(metadata or {}),
    )
