"""Persistent dry-run auto-reply state stored in the project SQLite database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.auto_reply_policy import AutoReplyEvent
from src.database import connect_database, initialize_database, resolve_database_path


def _now_text(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


@dataclass(frozen=True)
class AutoReplyStateRecord:
    id: int
    sender: str
    source: str
    first_seen_at: datetime
    last_seen_at: datetime
    last_status: str
    last_reason: str | None
    last_preview: str | None
    confidence: float
    replied_dry_run: bool
    real_sent: bool
    dry_run_replied_at: datetime | None
    real_sent_at: datetime | None
    stale_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @property
    def key(self) -> tuple[str, str]:
        return self.sender, self.source


class AutoReplyStateStore:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = resolve_database_path(database_path)
        initialize_database(self.database_path)
        self.connection = connect_database(self.database_path)

    def close(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass

    def __enter__(self) -> "AutoReplyStateStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _row_to_record(self, row: sqlite3.Row) -> AutoReplyStateRecord:
        return AutoReplyStateRecord(
            id=int(row["id"]),
            sender=str(row["sender"]),
            source=str(row["source"]),
            first_seen_at=_parse_datetime(row["first_seen_at"]) or datetime.now(),
            last_seen_at=_parse_datetime(row["last_seen_at"]) or datetime.now(),
            last_status=str(row["last_status"]),
            last_reason=str(row["last_reason"]) if row["last_reason"] is not None else None,
            last_preview=str(row["last_preview"]) if row["last_preview"] is not None else None,
            confidence=float(row["confidence"]),
            replied_dry_run=bool(row["replied_dry_run"]),
            real_sent=bool(row["real_sent"]),
            dry_run_replied_at=_parse_datetime(row["dry_run_replied_at"]),
            real_sent_at=_parse_datetime(row["real_sent_at"]),
            stale_at=_parse_datetime(row["stale_at"]),
            created_at=_parse_datetime(row["created_at"]) or datetime.now(),
            updated_at=_parse_datetime(row["updated_at"]) or datetime.now(),
        )

    def get(self, sender: str, source: str) -> AutoReplyStateRecord | None:
        row = self.connection.execute(
            "SELECT * FROM auto_reply_state WHERE sender = ? AND source = ?",
            (sender, source),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def _is_expired(self, record: AutoReplyStateRecord, *, now: datetime, stale_after_minutes: float) -> bool:
        if stale_after_minutes <= 0:
            return False
        return now - record.last_seen_at >= timedelta(minutes=stale_after_minutes)

    def merge_detected_event(
        self,
        event: AutoReplyEvent,
        *,
        now: datetime,
        cooldown_minutes: float,
        stale_after_minutes: float,
    ) -> AutoReplyEvent:
        record = self.get(event.sender, event.source)
        if record is None:
            return replace(
                event,
                first_seen_at=event.first_seen_at,
                last_seen_at=now,
                last_replied_at=None,
            )

        if self._is_expired(record, now=now, stale_after_minutes=stale_after_minutes):
            return replace(
                event,
                first_seen_at=event.first_seen_at,
                last_seen_at=now,
                last_replied_at=None,
            )

        last_replied_at = record.dry_run_replied_at or record.real_sent_at
        if record.replied_dry_run and last_replied_at is not None:
            if now - last_replied_at >= timedelta(minutes=cooldown_minutes):
                return replace(
                    event,
                    first_seen_at=event.first_seen_at,
                    last_seen_at=now,
                    last_replied_at=None,
                )

        return replace(
            event,
            first_seen_at=record.first_seen_at,
            last_seen_at=now,
            last_replied_at=last_replied_at,
        )

    def upsert_event_state(
        self,
        event: AutoReplyEvent,
        *,
        now: datetime,
        cooldown_minutes: float,
        stale_after_minutes: float,
    ) -> AutoReplyStateRecord:
        existing = self.get(event.sender, event.source)
        if existing is None:
            cursor = self.connection.execute(
                """
                INSERT INTO auto_reply_state
                    (sender, source, first_seen_at, last_seen_at, last_status, last_reason,
                     last_preview, confidence, replied_dry_run, real_sent, dry_run_replied_at,
                     real_sent_at, stale_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.sender,
                    event.source,
                    event.first_seen_at.isoformat(timespec="seconds"),
                    event.last_seen_at.isoformat(timespec="seconds"),
                    event.status,
                    event.reason,
                    event.message_preview,
                    float(event.confidence),
                    1 if event.status == "ready_for_reply" else 0,
                    0,
                    _now_text(now) if event.status == "ready_for_reply" else None,
                    None,
                    None,
                    _now_text(now),
                    _now_text(now),
                ),
            )
            self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM auto_reply_state WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return self._row_to_record(row)

        replied_dry_run = existing.replied_dry_run
        dry_run_replied_at = existing.dry_run_replied_at
        real_sent = existing.real_sent
        real_sent_at = existing.real_sent_at
        cooldown_elapsed = (
            existing.replied_dry_run
            and existing.dry_run_replied_at is not None
            and now - existing.dry_run_replied_at >= timedelta(minutes=cooldown_minutes)
        )
        if cooldown_elapsed and event.first_seen_at == event.detected_at:
            replied_dry_run = False
            dry_run_replied_at = None
        if event.status == "ready_for_reply":
            replied_dry_run = True
            dry_run_replied_at = now
        if event.status == "expired":
            replied_dry_run = False
            dry_run_replied_at = None

        stale_at = existing.stale_at
        if self._is_expired(existing, now=now, stale_after_minutes=stale_after_minutes):
            stale_at = now

        self.connection.execute(
            """
            UPDATE auto_reply_state
            SET first_seen_at = ?,
                last_seen_at = ?,
                last_status = ?,
                last_reason = ?,
                last_preview = ?,
                confidence = ?,
                replied_dry_run = ?,
                real_sent = ?,
                dry_run_replied_at = ?,
                real_sent_at = ?,
                stale_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                event.first_seen_at.isoformat(timespec="seconds"),
                event.last_seen_at.isoformat(timespec="seconds"),
                event.status,
                event.reason,
                event.message_preview,
                float(event.confidence),
                1 if replied_dry_run else 0,
                1 if real_sent else 0,
                dry_run_replied_at.isoformat(timespec="seconds") if dry_run_replied_at else None,
                real_sent_at.isoformat(timespec="seconds") if real_sent_at else None,
                stale_at.isoformat(timespec="seconds") if stale_at else None,
                _now_text(now),
                existing.id,
            ),
        )
        self.connection.commit()
        updated = self.connection.execute(
            "SELECT * FROM auto_reply_state WHERE id = ?",
            (existing.id,),
        ).fetchone()
        return self._row_to_record(updated)

    def mark_stale_rows(self, *, now: datetime, stale_after_minutes: float) -> int:
        if stale_after_minutes <= 0:
            return 0
        cutoff = (now - timedelta(minutes=stale_after_minutes)).isoformat(timespec="seconds")
        cursor = self.connection.execute(
            """
            UPDATE auto_reply_state
            SET last_status = 'expired',
                last_reason = 'stale state expired',
                stale_at = ?,
                updated_at = ?
            WHERE last_status != 'expired' AND last_seen_at <= ?
            """,
            (_now_text(now), _now_text(now), cutoff),
        )
        self.connection.commit()
        return int(cursor.rowcount)

    def mark_real_sent(self, event: AutoReplyEvent, *, now: datetime) -> AutoReplyStateRecord | None:
        """Mark a planned auto-reply event as really sent.

        The caller should call this only after message_sender.send_message()
        returns True.  This keeps dry-run state distinct from real-send state.
        """
        existing = self.get(event.sender, event.source)
        if existing is None:
            cursor = self.connection.execute(
                """
                INSERT INTO auto_reply_state
                    (sender, source, first_seen_at, last_seen_at, last_status, last_reason,
                     last_preview, confidence, replied_dry_run, real_sent, dry_run_replied_at,
                     real_sent_at, stale_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.sender,
                    event.source,
                    event.first_seen_at.isoformat(timespec="seconds"),
                    event.last_seen_at.isoformat(timespec="seconds"),
                    event.status,
                    event.reason,
                    event.message_preview,
                    float(event.confidence),
                    0,
                    1,
                    None,
                    _now_text(now),
                    None,
                    _now_text(now),
                    _now_text(now),
                ),
            )
            self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM auto_reply_state WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return self._row_to_record(row) if row else None

        self.connection.execute(
            """
            UPDATE auto_reply_state
            SET last_status = ?,
                last_reason = ?,
                last_preview = ?,
                confidence = ?,
                replied_dry_run = 0,
                real_sent = 1,
                dry_run_replied_at = NULL,
                real_sent_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                event.status,
                event.reason,
                event.message_preview,
                float(event.confidence),
                _now_text(now),
                _now_text(now),
                existing.id,
            ),
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT * FROM auto_reply_state WHERE id = ?",
            (existing.id,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def summarize(self) -> list[AutoReplyStateRecord]:
        rows = self.connection.execute("SELECT * FROM auto_reply_state ORDER BY sender, source").fetchall()
        return [self._row_to_record(row) for row in rows]
