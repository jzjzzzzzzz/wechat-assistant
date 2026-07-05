from datetime import datetime

from src.reminders import build_reminder_plans, parse_remind_at, reminder_is_due, validate_reminder


def test_parse_remind_at_supports_date_and_datetime() -> None:
    assert parse_remind_at("2026-07-05") == datetime(2026, 7, 5)
    assert parse_remind_at("2026-07-05 09:30") == datetime(2026, 7, 5, 9, 30)
    assert parse_remind_at("bad") is None


def test_validate_reminder_rejects_invalid_repeat() -> None:
    errors = validate_reminder(
        {
            "reminder_id": "r1",
            "target": "文件传输助手",
            "remind_at": "2026-07-05 09:30",
            "message": "hello",
            "repeat": "weekly",
            "enabled": "true",
        }
    )

    assert "repeat must be none or daily" in errors


def test_reminder_is_due_for_one_time_reminder() -> None:
    reminder = {"remind_at": "2026-07-05 09:30", "repeat": "none"}

    assert reminder_is_due(reminder, datetime(2026, 7, 5, 9, 31)) is True
    assert reminder_is_due(reminder, datetime(2026, 7, 5, 9, 29)) is False


def test_reminder_is_due_for_daily_reminder() -> None:
    reminder = {"remind_at": "2026-07-05 09:30", "repeat": "daily"}

    assert reminder_is_due(reminder, datetime(2026, 8, 1, 9, 31)) is True
    assert reminder_is_due(reminder, datetime(2026, 8, 1, 9, 29)) is False


def test_build_reminder_plans_filters_disabled_and_invalid() -> None:
    plans = build_reminder_plans(
        [
            {
                "reminder_id": "disabled",
                "target": "文件传输助手",
                "remind_at": "2026-07-05 09:30",
                "message": "hello",
                "repeat": "none",
                "enabled": "false",
            },
            {
                "reminder_id": "invalid",
                "target": "文件传输助手",
                "remind_at": "bad",
                "message": "hello",
                "repeat": "none",
                "enabled": "true",
            },
            {
                "reminder_id": "due",
                "target": "文件传输助手",
                "remind_at": "2026-07-05 09:30",
                "message": "hello",
                "repeat": "none",
                "enabled": "true",
            },
        ],
        datetime(2026, 7, 5, 9, 31),
    )

    assert len(plans) == 1
    assert plans[0].reminder_id == "due"
    assert plans[0].dry_run_only is True
