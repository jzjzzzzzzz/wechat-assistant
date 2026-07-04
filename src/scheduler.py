"""Birthday task scheduler skeleton."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import schedule


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BIRTHDAY_TASKS_PATH = PROJECT_ROOT / "data" / "birthday_tasks.csv"
SAFE_TEST_CONTACT = "文件传输助手"
LOGGER = logging.getLogger(__name__)


def birthday_matches(today: date, birthday: str) -> bool:
    value = str(birthday).strip()
    if not value:
        return False

    if re_match := re.fullmatch(r"(\d{2})-(\d{2})", value):
        month = int(re_match.group(1))
        day = int(re_match.group(2))
        return month == today.month and day == today.day

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.month == today.month and parsed.day == today.day
    except ValueError:
        return False


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


def check_birthdays(config: dict[str, Any], today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    matches: list[dict[str, Any]] = []

    for task in load_birthday_tasks():
        if not _is_enabled(task.get("enabled", "")):
            continue
        if not birthday_matches(today, str(task.get("birthday", ""))):
            continue

        target = str(task.get("wechat_remark", "")).strip()
        message = str(task.get("message", "")).strip()
        task_info = {"wechat_remark": target, "birthday": task.get("birthday", ""), "message": message}
        matches.append(task_info)
        print(f"BIRTHDAY TASK DRY RUN: target={target} message={message}")
        LOGGER.info("Matched birthday task: %s", task_info)

        if target != SAFE_TEST_CONTACT:
            LOGGER.warning("Real sending remains blocked for non-test target: %s", target)
        if config.get("dry_run", True):
            LOGGER.info("Birthday task is dry-run only.")

    return matches


def schedule_daily_birthday_check(config: dict[str, Any]) -> None:
    """Register future 00:00 daily birthday checks without starting a loop."""
    schedule.every().day.at("00:00").do(check_birthdays, config=config)
    LOGGER.info("Registered daily birthday check for 00:00.")
