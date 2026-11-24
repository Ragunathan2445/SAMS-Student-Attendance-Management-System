"""MongoDB client for supplementary records only (activity logs, notifications, system events).

MongoDB is *never* the source of truth: official attendance, student master data and
financial transactions live in PostgreSQL. Every write here is best-effort so the
application keeps working if MongoDB is temporarily unavailable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

from app.core.config import get_settings

logger = logging.getLogger("sams.mongo")

ACTIVITY_LOGS = "activity_logs"
NOTIFICATION_HISTORY = "notification_history"
SYSTEM_EVENTS = "system_events"

_client: MongoClient | None = None


def get_mongo_db():
    global _client
    settings = get_settings()
    if _client is None:
        _client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
    return _client[settings.mongo_db_name]


def ensure_indexes() -> None:
    try:
        db = get_mongo_db()
        db[ACTIVITY_LOGS].create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
        db[ACTIVITY_LOGS].create_index([("activity_type", ASCENDING)])
        db[NOTIFICATION_HISTORY].create_index([("recipient_id", ASCENDING), ("timestamp", DESCENDING)])
        db[SYSTEM_EVENTS].create_index([("event_type", ASCENDING), ("timestamp", DESCENDING)])
    except PyMongoError as exc:  # pragma: no cover - depends on local Mongo
        logger.warning("MongoDB unavailable, skipping index creation: %s", exc.__class__.__name__)


def _insert(collection: str, document: dict[str, Any]) -> None:
    document.setdefault("timestamp", datetime.now(timezone.utc))
    try:
        get_mongo_db()[collection].insert_one(document)
    except PyMongoError as exc:  # pragma: no cover
        logger.warning("MongoDB write to %s failed: %s", collection, exc.__class__.__name__)


def log_activity(
    *,
    user_id: int | None,
    user_role: str | None,
    activity_type: str,
    description: str,
    record_ref: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _insert(
        ACTIVITY_LOGS,
        {
            "user_id": user_id,
            "user_role": user_role,
            "activity_type": activity_type,
            "description": description,
            "record_ref": record_ref or {},
            "metadata": metadata or {},
        },
    )


def log_notification(
    *, recipient_id: int | None, recipient_role: str, channel: str, destination: str, subject: str, body: str
) -> None:
    _insert(
        NOTIFICATION_HISTORY,
        {
            "recipient_id": recipient_id,
            "recipient_role": recipient_role,
            "channel": channel,
            "destination": destination,
            "subject": subject,
            "body": body,
            "delivery": "demo-console",
        },
    )


def log_system_event(event_type: str, message: str, metadata: dict[str, Any] | None = None) -> None:
    _insert(SYSTEM_EVENTS, {"event_type": event_type, "message": message, "metadata": metadata or {}})


def recent_activity(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    try:
        cursor = (
            get_mongo_db()[ACTIVITY_LOGS]
            .find({"user_id": user_id}, {"_id": 0, "metadata": 0})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError:  # pragma: no cover
        return []
