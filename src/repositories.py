"""Repository helpers for the project-owned SQLite database."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _bool(value: bool) -> int:
    return 1 if value else 0


def create_contact(
    connection: sqlite3.Connection,
    contact_name: str,
    *,
    source: str = "manual",
    confidence: float = 1.0,
    reviewed: bool = False,
    enabled: bool = True,
) -> int:
    now = _now()
    cursor = connection.execute(
        """
        INSERT INTO contacts (contact_name, source, confidence, reviewed, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (contact_name, source, float(confidence), _bool(reviewed), _bool(enabled), now, now),
    )
    connection.commit()
    return int(cursor.lastrowid)


def list_contacts(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute("SELECT * FROM contacts ORDER BY contact_name").fetchall()
    return [dict(row) for row in rows]


def get_contact_by_name(connection: sqlite3.Connection, contact_name: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM contacts WHERE contact_name = ?", (contact_name,)).fetchone()
    return dict(row) if row else None


def upsert_contact_candidate(
    connection: sqlite3.Connection,
    contact_name: str,
    *,
    source: str = "ocr",
    confidence: float = 0.0,
) -> tuple[int, bool]:
    existing = get_contact_by_name(connection, contact_name)
    if existing is None:
        contact_id = create_contact(
            connection,
            contact_name,
            source=source,
            confidence=confidence,
            reviewed=False,
            enabled=True,
        )
        return contact_id, True

    if float(confidence) > float(existing["confidence"]):
        connection.execute(
            """
            UPDATE contacts
            SET source = ?, confidence = ?, updated_at = ?
            WHERE id = ?
            """,
            (source, float(confidence), _now(), existing["id"]),
        )
        connection.commit()
    return int(existing["id"]), False


def set_contact_reviewed(connection: sqlite3.Connection, contact_name: str, reviewed: bool = True) -> bool:
    cursor = connection.execute(
        "UPDATE contacts SET reviewed = ?, updated_at = ? WHERE contact_name = ?",
        (_bool(reviewed), _now(), contact_name),
    )
    connection.commit()
    return cursor.rowcount > 0


def set_contact_enabled(connection: sqlite3.Connection, contact_name: str, enabled: bool) -> bool:
    cursor = connection.execute(
        "UPDATE contacts SET enabled = ?, updated_at = ? WHERE contact_name = ?",
        (_bool(enabled), _now(), contact_name),
    )
    connection.commit()
    return cursor.rowcount > 0


def list_enabled_reviewed_contacts(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT * FROM contacts
        WHERE enabled = 1 AND reviewed = 1
        ORDER BY contact_name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def create_birthday_task(
    connection: sqlite3.Connection,
    wechat_remark: str,
    birthday: str,
    message: str,
    *,
    enabled: bool = True,
) -> int:
    now = _now()
    cursor = connection.execute(
        """
        INSERT INTO birthday_tasks (wechat_remark, birthday, message, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (wechat_remark, birthday, message, _bool(enabled), now, now),
    )
    connection.commit()
    return int(cursor.lastrowid)


def list_birthday_tasks(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute("SELECT * FROM birthday_tasks ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def create_message_template(
    connection: sqlite3.Connection,
    name: str,
    category: str,
    body: str,
    *,
    enabled: bool = True,
) -> int:
    now = _now()
    cursor = connection.execute(
        """
        INSERT INTO message_templates (name, category, body, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, category, body, _bool(enabled), now, now),
    )
    connection.commit()
    return int(cursor.lastrowid)


def list_message_templates(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute("SELECT * FROM message_templates ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def record_audit_event(
    connection: sqlite3.Connection,
    event_type: str,
    *,
    target: str | None = None,
    message_preview: str | None = None,
    safety_decision: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO audit_events
            (event_type, target, message_preview, safety_decision, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            target,
            message_preview,
            safety_decision,
            json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            _now(),
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def list_audit_events(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute("SELECT * FROM audit_events ORDER BY id").fetchall()
    return [dict(row) for row in rows]
