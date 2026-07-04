from datetime import date

from src.message_sender import send_message
from src.scheduler import birthday_matches


def test_message_sender_dry_run_does_not_call_real_actions() -> None:
    calls: list[str] = []
    config = {
        "dry_run": True,
        "allow_real_send": False,
        "max_retry": 3,
        "send_delay_seconds": 0,
    }

    result = send_message(
        config,
        "文件传输助手",
        "hello",
        search_func=lambda target, cfg: calls.append("search") or True,
        paste_func=lambda message: calls.append("paste") or True,
        enter_func=lambda: calls.append("enter") or True,
        screenshot_func=lambda cfg: calls.append("screenshot") or "screenshot.png",
    )

    assert result is True
    assert calls == []


def test_birthday_matches_mm_dd() -> None:
    assert birthday_matches(date(2026, 7, 5), "07-05") is True
    assert birthday_matches(date(2026, 7, 5), "07-06") is False


def test_birthday_matches_yyyy_mm_dd() -> None:
    assert birthday_matches(date(2026, 7, 5), "2000-07-05") is True
    assert birthday_matches(date(2026, 7, 5), "2000-07-06") is False
