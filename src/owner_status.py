"""Owner online/offline status stored in the project database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from src.database import connect_database, initialize_database, resolve_database_path


OwnerStatusValue = Literal["online", "offline"]


def _now_text(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def validate_owner_status(status: str) -> OwnerStatusValue:
    normalized = str(status).strip().lower()
    if normalized not in {"online", "offline"}:
        raise ValueError("owner status must be online or offline")
    return normalized  # type: ignore[return-value]


def owner_config(config: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "status_default": "online",
        "offline_reply_immediate": True,
        "status_menu_enabled": True,
    }
    raw = config.get("owner", {})
    if isinstance(raw, dict):
        defaults.update(raw)
    defaults["status_default"] = validate_owner_status(str(defaults.get("status_default", "online")))
    defaults["offline_reply_immediate"] = bool(defaults.get("offline_reply_immediate", True))
    defaults["status_menu_enabled"] = bool(defaults.get("status_menu_enabled", True))
    return defaults


@dataclass(frozen=True)
class OwnerStatusRecord:
    status: OwnerStatusValue
    updated_at: datetime | None
    updated_by: str
    note: str | None
    source: Literal["database", "config default"]


class OwnerStatusStore:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = resolve_database_path(database_path)
        initialize_database(self.database_path)
        self.connection = connect_database(self.database_path)

    def close(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass

    def __enter__(self) -> "OwnerStatusStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _row_to_record(self, row: sqlite3.Row) -> OwnerStatusRecord:
        return OwnerStatusRecord(
            status=validate_owner_status(str(row["status"])),
            updated_at=_parse_datetime(row["updated_at"]),
            updated_by=str(row["updated_by"]),
            note=str(row["note"]) if row["note"] is not None else None,
            source="database",
        )

    def get_database_status(self) -> OwnerStatusRecord | None:
        row = self.connection.execute(
            """
            SELECT * FROM owner_status
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        return self._row_to_record(row) if row else None

    def get_status(self, config: dict[str, Any]) -> OwnerStatusRecord:
        database_record = self.get_database_status()
        if database_record is not None:
            return database_record
        default_status = validate_owner_status(str(owner_config(config)["status_default"]))
        return OwnerStatusRecord(
            status=default_status,
            updated_at=None,
            updated_by="config",
            note=None,
            source="config default",
        )

    def set_status(
        self,
        status: str,
        *,
        updated_by: str = "cli",
        note: str | None = None,
        now: datetime | None = None,
    ) -> OwnerStatusRecord:
        normalized = validate_owner_status(status)
        updated_at = _now_text(now)
        self.connection.execute(
            """
            INSERT INTO owner_status (status, updated_at, updated_by, note)
            VALUES (?, ?, ?, ?)
            """,
            (normalized, updated_at, updated_by, note),
        )
        self.connection.commit()
        record = self.get_database_status()
        if record is None:
            raise RuntimeError("owner status write failed")
        return record

    def toggle_status(
        self,
        config: dict[str, Any],
        *,
        updated_by: str = "cli",
        now: datetime | None = None,
    ) -> OwnerStatusRecord:
        current = self.get_status(config)
        return self.set_status(
            "offline" if current.status == "online" else "online",
            updated_by=updated_by,
            note="toggle",
            now=now,
        )


def get_owner_status(config: dict[str, Any]) -> OwnerStatusRecord:
    with OwnerStatusStore(config.get("database_path")) as store:
        return store.get_status(config)


def set_owner_status(
    config: dict[str, Any],
    status: str,
    *,
    updated_by: str = "cli",
    note: str | None = None,
) -> OwnerStatusRecord:
    with OwnerStatusStore(config.get("database_path")) as store:
        return store.set_status(status, updated_by=updated_by, note=note)


def toggle_owner_status(config: dict[str, Any], *, updated_by: str = "cli") -> OwnerStatusRecord:
    with OwnerStatusStore(config.get("database_path")) as store:
        return store.toggle_status(config, updated_by=updated_by)
