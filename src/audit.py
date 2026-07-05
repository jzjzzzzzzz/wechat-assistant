"""Structured audit logging for safety-relevant events."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from src.database import connect_database, initialize_database
from src.repositories import record_audit_event


LOGGER = logging.getLogger(__name__)
MAX_MESSAGE_PREVIEW_LENGTH = 120


class AuditEventType(str, Enum):
    DRY_RUN_SEND = "dry_run_send"
    BLOCKED_REAL_SEND = "blocked_real_send"
    REAL_SEND_SUCCESS = "real_send_success"
    REAL_SEND_FAILURE = "real_send_failure"


def message_preview(message: str | None) -> str | None:
    if message is None:
        return None
    value = str(message).replace("\n", " ").strip()
    if len(value) <= MAX_MESSAGE_PREVIEW_LENGTH:
        return value
    return value[:MAX_MESSAGE_PREVIEW_LENGTH] + "..."


def write_audit_event(
    config: dict[str, Any],
    event_type: AuditEventType,
    *,
    target: str | None = None,
    message: str | None = None,
    safety_decision: str,
    metadata: dict[str, Any] | None = None,
) -> int | None:
    if not config.get("audit_enabled", False):
        LOGGER.info("Audit disabled; skipped event_type=%s", event_type.value)
        return None

    database_path = config.get("database_path", "data/wechat_assistant.sqlite3")
    initialize_database(database_path)
    with connect_database(database_path) as connection:
        event_id = record_audit_event(
            connection,
            event_type.value,
            target=target,
            message_preview=message_preview(message),
            safety_decision=safety_decision,
            metadata=metadata or {},
        )
    LOGGER.info("Recorded audit event id=%s type=%s", event_id, event_type.value)
    return event_id
