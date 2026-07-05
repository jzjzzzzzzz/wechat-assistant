from datetime import date

from src.scheduler import (
    birthday_matches,
    build_birthday_plans,
    parse_birthday_month_day,
    validate_birthday_task,
)


def test_parse_birthday_month_day_validates_dates() -> None:
    assert parse_birthday_month_day("07-05") == (7, 5)
    assert parse_birthday_month_day("2000-02-29") == (2, 29)
    assert parse_birthday_month_day("02-30") is None
    assert parse_birthday_month_day("bad") is None


def test_validate_birthday_task_reports_invalid_date() -> None:
    errors = validate_birthday_task(
        {
            "wechat_remark": "文件传输助手",
            "birthday": "02-30",
            "message": "生日快乐",
            "enabled": "true",
        }
    )

    assert "birthday must be MM-DD or YYYY-MM-DD" in errors


def test_build_birthday_plans_filters_disabled_and_invalid_tasks() -> None:
    plans = build_birthday_plans(
        [
            {
                "wechat_remark": "文件传输助手",
                "birthday": "07-05",
                "message": "生日快乐",
                "enabled": "false",
            },
            {
                "wechat_remark": "文件传输助手",
                "birthday": "02-30",
                "message": "生日快乐",
                "enabled": "true",
            },
            {
                "wechat_remark": "文件传输助手",
                "birthday": "07-05",
                "message": "生日快乐",
                "enabled": "true",
            },
        ],
        {"dry_run": True, "allow_real_send": False},
        date(2026, 7, 5),
    )

    assert len(plans) == 1
    assert plans[0].wechat_remark == "文件传输助手"
    assert plans[0].dry_run_only is True
    assert plans[0].real_send_blocked is True
    assert plans[0].block_reason == "dry_run is true"


def test_build_birthday_plans_blocks_non_test_target_even_when_real_send_flags_enabled() -> None:
    plans = build_birthday_plans(
        [
            {
                "wechat_remark": "Normal Contact",
                "birthday": "2020-07-05",
                "message": "生日快乐",
                "enabled": "true",
            }
        ],
        {"dry_run": False, "allow_real_send": True},
        date(2026, 7, 5),
    )

    assert len(plans) == 1
    assert plans[0].real_send_blocked is True
    assert "not in allowed_real_contacts" in plans[0].block_reason


def test_build_birthday_plans_allows_file_transfer_helper_when_flags_enabled() -> None:
    plans = build_birthday_plans(
        [
            {
                "wechat_remark": "文件传输助手",
                "birthday": "07-05",
                "message": "生日快乐",
                "enabled": "true",
            }
        ],
        {"dry_run": False, "allow_real_send": True},
        date(2026, 7, 5),
    )

    assert len(plans) == 1
    assert plans[0].real_send_blocked is False


def test_build_birthday_plans_allows_whitelisted_real_contact_when_flags_enabled() -> None:
    plans = build_birthday_plans(
        [
            {
                "wechat_remark": "Normal Contact",
                "birthday": "07-05",
                "message": "生日快乐",
                "enabled": "true",
            }
        ],
        {
            "dry_run": False,
            "allow_real_send": True,
            "allowed_real_contacts": ["Normal Contact"],
        },
        date(2026, 7, 5),
    )

    assert len(plans) == 1
    assert plans[0].real_send_blocked is False
    assert plans[0].block_reason == "real send allowed"


def test_birthday_matches_rejects_invalid_dates() -> None:
    assert birthday_matches(date(2026, 7, 5), "07-05") is True
    assert birthday_matches(date(2026, 7, 5), "02-30") is False
