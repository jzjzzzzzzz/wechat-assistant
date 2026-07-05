"""Birthday task scheduler skeleton."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import schedule


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BIRTHDAY_TASKS_PATH = PROJECT_ROOT / "data" / "birthday_tasks.csv"
SAFE_TEST_CONTACT = "文件传输助手"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BirthdayTaskPlan:
    wechat_remark: str
    birthday: str
    message: str
    run_date: date
    dry_run_only: bool
    real_send_blocked: bool
    block_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "wechat_remark": self.wechat_remark,
            "birthday": self.birthday,
            "message": self.message,
            "run_date": self.run_date.isoformat(),
            "dry_run_only": self.dry_run_only,
            "real_send_blocked": self.real_send_blocked,
            "block_reason": self.block_reason,
        }


def parse_birthday_month_day(birthday: str) -> tuple[int, int] | None:
    value = str(birthday).strip()
    if not value:
        return None

    if re_match := re.fullmatch(r"(\d{2})-(\d{2})", value):
        month = int(re_match.group(1))
        day = int(re_match.group(2))
        try:
            date(2000, month, day)
        except ValueError:
            return None
        return month, day

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.month, parsed.day
    except ValueError:
        return None


def birthday_matches(today: date, birthday: str) -> bool:
    month_day = parse_birthday_month_day(birthday)
    if month_day is None:
        return False
    month, day = month_day
    return month == today.month and day == today.day


def _is_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def load_birthday_tasks(path: Path = BIRTHDAY_TASKS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["wechat_remark", "birthday", "message", "enabled"]).to_csv(
            path, index=False, encoding="utf-8"
        )
        LOGGER.info("Created empty birthday task file: %s", path)
        return []

    dataframe = pd.read_csv(path, dtype=str).fillna("")
    required = {"wechat_remark", "birthday", "message", "enabled"}
    missing = required - set(dataframe.columns)
    if missing:
        LOGGER.error("Birthday task file missing columns: %s", ", ".join(sorted(missing)))
        return []
    return dataframe.to_dict(orient="records")


def validate_birthday_task(task: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(task.get("wechat_remark", "")).strip():
        errors.append("wechat_remark is required")
    if parse_birthday_month_day(str(task.get("birthday", ""))) is None:
        errors.append("birthday must be MM-DD or YYYY-MM-DD")
    if not str(task.get("message", "")).strip():
        errors.append("message is required")
    return errors


def build_birthday_plans(
    tasks: list[dict[str, Any]],
    config: dict[str, Any],
    today: date,
) -> list[BirthdayTaskPlan]:
    plans: list[BirthdayTaskPlan] = []
    for task in tasks:
        if not _is_enabled(task.get("enabled", "")):
            LOGGER.info("Skipping disabled birthday task: %s", task)
            continue

        errors = validate_birthday_task(task)
        if errors:
            LOGGER.warning("Skipping invalid birthday task. errors=%s task=%s", errors, task)
            continue

        if not birthday_matches(today, str(task.get("birthday", ""))):
            continue

        target = str(task.get("wechat_remark", "")).strip()
        message = str(task.get("message", "")).strip()
        dry_run_only = bool(config.get("dry_run", True))

        # Check against the allowed-contacts whitelist (same logic as message_sender).
        from src.message_sender import _allowed_real_contacts
        allowed = _allowed_real_contacts(config)
        in_whitelist = target in allowed

        real_send_blocked = True
        if not in_whitelist:
            block_reason = f"real sending blocked: {target!r} not in allowed_real_contacts"
        elif dry_run_only:
            block_reason = "dry_run is true"
        elif not config.get("allow_real_send", False):
            block_reason = "allow_real_send is false"
        else:
            real_send_blocked = False
            block_reason = "real send allowed"

        plan = BirthdayTaskPlan(
            wechat_remark=target,
            birthday=str(task.get("birthday", "")).strip(),
            message=message,
            run_date=today,
            dry_run_only=dry_run_only,
            real_send_blocked=real_send_blocked,
            block_reason=block_reason,
        )
        plans.append(plan)
        LOGGER.info("Built birthday dry-run plan: %s", plan.as_dict())
        if real_send_blocked:
            LOGGER.warning("Birthday plan real-send blocked: %s", block_reason)
    return plans


def check_birthdays(config: dict[str, Any], today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    plans = build_birthday_plans(load_birthday_tasks(), config, today)
    for plan in plans:
        print(
            "BIRTHDAY TASK DRY RUN: "
            f"target={plan.wechat_remark} message={plan.message} blocked={plan.real_send_blocked}"
        )
    return [plan.as_dict() for plan in plans]


def preview_upcoming_birthdays(config: dict[str, Any], days: int = 7, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    tasks = load_birthday_tasks()
    previews: list[dict[str, Any]] = []
    for offset in range(max(1, days)):
        run_date = today + timedelta(days=offset)
        previews.extend(plan.as_dict() for plan in build_birthday_plans(tasks, config, run_date))
    return previews


def schedule_daily_birthday_check(config: dict[str, Any]) -> None:
    """Register future 00:00 daily birthday checks without starting a loop."""
    schedule.every().day.at("00:00").do(check_birthdays, config=config)
    LOGGER.info("Registered daily birthday check for 00:00.")


def execute_birthday_plans(
    config: dict[str, Any],
    plans: list["BirthdayTaskPlan"],
) -> list[dict[str, Any]]:
    """Execute a list of birthday plans: send real messages or log dry-run.

    Returns a list of result dicts with keys: target, message, sent, reason.
    """
    from src.message_sender import send_message

    results: list[dict[str, Any]] = []
    for plan in plans:
        if plan.real_send_blocked:
            LOGGER.info(
                "Birthday send skipped (blocked). target=%s reason=%s",
                plan.wechat_remark,
                plan.block_reason,
            )
            print(f"[DRY RUN] {plan.wechat_remark}: {plan.message}  ({plan.block_reason})")
            results.append({
                "target": plan.wechat_remark,
                "message": plan.message,
                "sent": False,
                "reason": plan.block_reason,
            })
        else:
            LOGGER.info("Sending birthday message. target=%s", plan.wechat_remark)
            ok = send_message(config, plan.wechat_remark, plan.message)
            status = "SENT" if ok else "FAILED"
            print(f"[{status}] {plan.wechat_remark}: {plan.message}")
            results.append({
                "target": plan.wechat_remark,
                "message": plan.message,
                "sent": ok,
                "reason": "sent" if ok else "send_failed",
            })
    return results


def run_birthday_send(
    config: dict[str, Any],
    *,
    today: date | None = None,
    force_contact: str | None = None,
) -> list[dict[str, Any]]:
    """Build plans for today (or force_contact) and execute them.

    If force_contact is given, send to that contact regardless of today's date
    (useful for on-demand birthday sends and testing).
    """
    tasks = load_birthday_tasks()

    if force_contact:
        # Find the task for this contact and execute it regardless of date.
        matching = [t for t in tasks if str(t.get("wechat_remark", "")).strip() == force_contact]
        if not matching:
            LOGGER.warning("No birthday task found for contact: %s", force_contact)
            print(f"No birthday task found for contact: {force_contact}")
            return []
        run_date = today or date.today()
        # Temporarily pretend today is the birthday so build_birthday_plans accepts it.
        from src.scheduler import parse_birthday_month_day
        for task in matching:
            md = parse_birthday_month_day(str(task.get("birthday", "")))
            if md:
                from datetime import date as _date
                run_date = _date(run_date.year, md[0], md[1])
                break
        plans = build_birthday_plans(matching, config, run_date)
    else:
        run_date = today or date.today()
        plans = build_birthday_plans(tasks, config, run_date)

    if not plans:
        print("No birthday plans to execute for today.")
        return []

    return execute_birthday_plans(config, plans)

