from datetime import date

from src.festivals import build_festival_plans, festival_matches, validate_festival_task


def test_festival_matches_mm_dd_and_full_date() -> None:
    assert festival_matches(date(2026, 1, 1), "01-01") is True
    assert festival_matches(date(2026, 1, 1), "2020-01-01") is True
    assert festival_matches(date(2026, 1, 1), "01-02") is False


def test_validate_festival_task_rejects_invalid_date() -> None:
    errors = validate_festival_task(
        {
            "festival_name": "New Year",
            "festival_date": "02-30",
            "wechat_remark": "文件传输助手",
            "message_template": "Hi",
            "enabled": "true",
        }
    )

    assert "festival_date must be MM-DD or YYYY-MM-DD" in errors


def test_build_festival_plans_filters_disabled_and_renders_template() -> None:
    plans = build_festival_plans(
        [
            {
                "festival_name": "New Year",
                "festival_date": "01-01",
                "wechat_remark": "文件传输助手",
                "message_template": "{festival}快乐，{name}",
                "enabled": "false",
            },
            {
                "festival_name": "New Year",
                "festival_date": "01-01",
                "wechat_remark": "文件传输助手",
                "message_template": "{festival}快乐，{name}",
                "enabled": "true",
            },
        ],
        {"dry_run": True, "allow_real_send": False},
        date(2026, 1, 1),
    )

    assert len(plans) == 1
    assert plans[0].message == "New Year快乐，文件传输助手"
    assert plans[0].real_send_blocked is True
    assert plans[0].block_reason == "dry_run is true"


def test_build_festival_plans_blocks_non_test_target() -> None:
    plans = build_festival_plans(
        [
            {
                "festival_name": "New Year",
                "festival_date": "01-01",
                "wechat_remark": "Normal Contact",
                "message_template": "{festival}快乐，{name}",
                "enabled": "true",
            }
        ],
        {"dry_run": False, "allow_real_send": True},
        date(2026, 1, 1),
    )

    assert len(plans) == 1
    assert plans[0].real_send_blocked is True
    assert "non-test target" in plans[0].block_reason
