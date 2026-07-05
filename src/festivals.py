"""Festival message dry-run planning."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.scheduler import SAFE_TEST_CONTACT, birthday_matches, parse_birthday_month_day
from src.templates import TemplateError, render_template_body


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FESTIVAL_TASKS_PATH = PROJECT_ROOT / "data" / "festival_tasks.csv"
FESTIVAL_COLUMNS = ["festival_name", "festival_date", "wechat_remark", "message_template", "enabled"]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FestivalPlan:
    festival_name: str
    festival_date: str
    wechat_remark: str
    message: str
    run_date: date
    real_send_blocked: bool
    block_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "festival_name": self.festival_name,
            "festival_date": self.festival_date,
            "wechat_remark": self.wechat_remark,
            "message": self.message,
            "run_date": self.run_date.isoformat(),
            "real_send_blocked": self.real_send_blocked,
            "block_reason": self.block_reason,
        }


def _is_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def load_festival_tasks(path: str | Path = FESTIVAL_TASKS_PATH) -> list[dict[str, Any]]:
    task_path = Path(path)
    if not task_path.exists():
        task_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=FESTIVAL_COLUMNS).to_csv(task_path, index=False, encoding="utf-8")
        return []
    dataframe = pd.read_csv(task_path, dtype=str).fillna("")
    missing = set(FESTIVAL_COLUMNS) - set(dataframe.columns)
    if missing:
        LOGGER.error("Festival task file missing columns: %s", ", ".join(sorted(missing)))
        return []
    return dataframe.to_dict(orient="records")


def validate_festival_task(task: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(task.get("festival_name", "")).strip():
        errors.append("festival_name is required")
    if parse_birthday_month_day(str(task.get("festival_date", ""))) is None:
        errors.append("festival_date must be MM-DD or YYYY-MM-DD")
    if not str(task.get("wechat_remark", "")).strip():
        errors.append("wechat_remark is required")
    if not str(task.get("message_template", "")).strip():
        errors.append("message_template is required")
    return errors


def festival_matches(today: date, festival_date: str) -> bool:
    return birthday_matches(today, festival_date)


def build_festival_plans(
    tasks: list[dict[str, Any]],
    config: dict[str, Any],
    today: date,
) -> list[FestivalPlan]:
    plans: list[FestivalPlan] = []
    for task in tasks:
        if not _is_enabled(task.get("enabled", "")):
            continue
        errors = validate_festival_task(task)
        if errors:
            LOGGER.warning("Skipping invalid festival task. errors=%s task=%s", errors, task)
            continue
        if not festival_matches(today, str(task["festival_date"])):
            continue

        target = str(task["wechat_remark"]).strip()
        festival_name = str(task["festival_name"]).strip()
        try:
            message = render_template_body(
                str(task["message_template"]),
                {
                    "festival": festival_name,
                    "name": target,
                    "date": today.isoformat(),
                },
            )
        except TemplateError as exc:
            LOGGER.warning("Skipping festival task with invalid template: %s", exc)
            continue

        if target != SAFE_TEST_CONTACT:
            real_send_blocked = True
            block_reason = f"real sending blocked for non-test target: {target}"
        elif config.get("dry_run", True):
            real_send_blocked = True
            block_reason = "dry_run is true"
        elif not config.get("allow_real_send", False):
            real_send_blocked = True
            block_reason = "allow_real_send is false"
        else:
            real_send_blocked = False
            block_reason = "real send would be allowed by festival policy"

        plan = FestivalPlan(
            festival_name=festival_name,
            festival_date=str(task["festival_date"]).strip(),
            wechat_remark=target,
            message=message,
            run_date=today,
            real_send_blocked=real_send_blocked,
            block_reason=block_reason,
        )
        plans.append(plan)
        LOGGER.info("Built festival dry-run plan: %s", plan.as_dict())
    return plans


def preview_festival_messages(
    config: dict[str, Any],
    today: date | None = None,
    path: str | Path = FESTIVAL_TASKS_PATH,
) -> list[dict[str, Any]]:
    run_date = today or date.today()
    return [plan.as_dict() for plan in build_festival_plans(load_festival_tasks(path), config, run_date)]
