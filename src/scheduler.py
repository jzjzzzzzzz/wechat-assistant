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
        real_send_blocked = True
        if target != SAFE_TEST_CONTACT:
            block_reason = f"real sending blocked for non-test target: {target}"
        elif dry_run_only:
            block_reason = "dry_run is true"
        elif not config.get("allow_real_send", False):
            block_reason = "allow_real_send is false"
        else:
            real_send_blocked = False
            block_reason = "real send would be allowed by scheduler policy"

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
