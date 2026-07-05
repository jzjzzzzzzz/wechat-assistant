"""Local contact management for project-owned contact records."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from src.repositories import (
    list_contacts,
    list_enabled_reviewed_contacts,
    set_contact_enabled,
    set_contact_reviewed,
    upsert_contact_candidate,
)


@dataclass(frozen=True)
class ContactImportResult:
    imported: int
    updated_or_existing: int
    skipped: int


def import_ocr_candidates(
    connection: sqlite3.Connection,
    candidates: list[dict[str, Any]],
) -> ContactImportResult:
    imported = 0
    existing = 0
    skipped = 0

    for candidate in candidates:
        contact_name = str(candidate.get("contact_name", "")).strip()
        if not contact_name:
            skipped += 1
            continue
        _contact_id, created = upsert_contact_candidate(
            connection,
            contact_name,
            source=str(candidate.get("source", "ocr")),
            confidence=float(candidate.get("confidence", 0.0)),
        )
        if created:
            imported += 1
        else:
            existing += 1

    return ContactImportResult(imported=imported, updated_or_existing=existing, skipped=skipped)


def mark_contact_reviewed(connection: sqlite3.Connection, contact_name: str, reviewed: bool = True) -> bool:
    return set_contact_reviewed(connection, contact_name, reviewed=reviewed)


def disable_contact(connection: sqlite3.Connection, contact_name: str) -> bool:
    return set_contact_enabled(connection, contact_name, enabled=False)


def enable_contact(connection: sqlite3.Connection, contact_name: str) -> bool:
    return set_contact_enabled(connection, contact_name, enabled=True)


def list_all_local_contacts(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_contacts(connection)


def list_contacts_available_for_future_tasks(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return reviewed and enabled contacts for future dry-run task planning only."""
    return list_enabled_reviewed_contacts(connection)
