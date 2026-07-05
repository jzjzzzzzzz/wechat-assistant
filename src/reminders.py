"""Local custom reminder dry-run planning."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REMINDERS_PATH = PROJECT_ROOT / "data" / "reminders.csv"
REMINDER_COLUMNS = ["reminder_id", "target", "remind_at", "message", "repeat", "enabled"]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReminderPlan:
    reminder_id: str
    target: str
    message: str
    remind_at: str
    repeat: str
    dry_run_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "reminder_id": self.reminder_id,
            "target": self.target,
            "message": self.message,
            "remind_at": self.remind_at,
            "repeat": self.repeat,
            "dry_run_only": self.dry_run_only,
        }


def _is_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_remind_at(value: str) -> datetime | None:
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def load_reminders(path: str | Path = REMINDERS_PATH) -> list[dict[str, Any]]:
    reminder_path = Path(path)
    if not reminder_path.exists():
        reminder_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=REMINDER_COLUMNS).to_csv(reminder_path, index=False, encoding="utf-8")
        return []
    dataframe = pd.read_csv(reminder_path, dtype=str).fillna("")
    missing = set(REMINDER_COLUMNS) - set(dataframe.columns)
    if missing:
        LOGGER.error("Reminder file missing columns: %s", ", ".join(sorted(missing)))
        return []
    return dataframe.to_dict(orient="records")


def validate_reminder(reminder: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(reminder.get("reminder_id", "")).strip():
        errors.append("reminder_id is required")
    if not str(reminder.get("target", "")).strip():
        errors.append("target is required")
    if parse_remind_at(str(reminder.get("remind_at", ""))) is None:
        errors.append("remind_at must be YYYY-MM-DD or YYYY-MM-DD HH:MM")
    if not str(reminder.get("message", "")).strip():
        errors.append("message is required")
    if str(reminder.get("repeat", "none")).strip().lower() not in {"none", "daily"}:
        errors.append("repeat must be none or daily")
    return errors


def reminder_is_due(reminder: dict[str, Any], now: datetime) -> bool:
    remind_at = parse_remind_at(str(reminder.get("remind_at", "")))
    if remind_at is None:
        return False
    repeat = str(reminder.get("repeat", "none")).strip().lower()
    if repeat == "daily":
        return (now.hour, now.minute) >= (remind_at.hour, remind_at.minute)
    return now >= remind_at


def build_reminder_plans(reminders: list[dict[str, Any]], now: datetime) -> list[ReminderPlan]:
    plans: list[ReminderPlan] = []
    for reminder in reminders:
        if not _is_enabled(reminder.get("enabled", "")):
            continue
        errors = validate_reminder(reminder)
        if errors:
            LOGGER.warning("Skipping invalid reminder. errors=%s reminder=%s", errors, reminder)
            continue
        if not reminder_is_due(reminder, now):
            continue
        plan = ReminderPlan(
            reminder_id=str(reminder["reminder_id"]).strip(),
            target=str(reminder["target"]).strip(),
            message=str(reminder["message"]).strip(),
            remind_at=str(reminder["remind_at"]).strip(),
            repeat=str(reminder.get("repeat", "none")).strip().lower(),
        )
        plans.append(plan)
        LOGGER.info("Built reminder dry-run plan: %s", plan.as_dict())
    return plans


def preview_due_reminders(now: datetime | None = None, path: str | Path = REMINDERS_PATH) -> list[dict[str, Any]]:
    current_time = now or datetime.now()
    return [plan.as_dict() for plan in build_reminder_plans(load_reminders(path), current_time)]
