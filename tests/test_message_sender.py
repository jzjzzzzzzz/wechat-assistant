from datetime import date
from pathlib import Path

from src.database import connect_database
from src.message_sender import send_message
from src.repositories import list_audit_events
from src.scheduler import birthday_matches
from src.screen_state import ScreenState, ScreenStateDetection
from src.wechat_window import UiActionResult


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


def test_message_sender_dry_run_writes_audit_when_enabled(tmp_path: Path) -> None:
    database_path = tmp_path / "wechat_assistant.sqlite3"
    config = {
        "dry_run": True,
        "allow_real_send": False,
        "audit_enabled": True,
        "database_path": str(database_path),
        "max_retry": 3,
        "send_delay_seconds": 0,
    }

    result = send_message(config, "文件传输助手", "hello")

    assert result is True
    with connect_database(database_path) as connection:
        events = list_audit_events(connection)
    assert len(events) == 1
    assert events[0]["event_type"] == "dry_run_send"
    assert events[0]["safety_decision"] == "dry_run"


def test_message_sender_blocked_real_send_writes_audit_when_enabled(tmp_path: Path) -> None:
    database_path = tmp_path / "wechat_assistant.sqlite3"
    config = {
        "dry_run": False,
        "allow_real_send": False,
        "audit_enabled": True,
        "database_path": str(database_path),
        "max_retry": 3,
        "send_delay_seconds": 0,
    }

    result = send_message(config, "文件传输助手", "hello")

    assert result is False
    with connect_database(database_path) as connection:
        events = list_audit_events(connection)
    assert len(events) == 1
    assert events[0]["event_type"] == "blocked_real_send"
    assert events[0]["safety_decision"] == "blocked"


def test_message_sender_blocks_real_send_to_normal_contact() -> None:
    calls: list[str] = []
    config = {
        "dry_run": False,
        "allow_real_send": True,
        "max_retry": 1,
        "send_delay_seconds": 0,
    }

    result = send_message(
        config,
        "Normal Contact",
        "hello",
        search_func=lambda target, cfg: calls.append("search") or True,
        paste_func=lambda message: calls.append("paste") or True,
        enter_func=lambda: calls.append("enter") or True,
        screenshot_func=lambda cfg: calls.append("screenshot") or "screen.png",
    )

    assert result is False
    assert calls == []


def test_message_sender_allowed_file_transfer_helper_real_send_sequence_is_mocked(tmp_path: Path) -> None:
    calls: list[str] = []
    database_path = tmp_path / "wechat_assistant.sqlite3"
    config = {
        "dry_run": False,
        "allow_real_send": True,
        "require_known_screen_state_for_real_send": True,
        "audit_enabled": True,
        "database_path": str(database_path),
        "max_retry": 1,
        "send_delay_seconds": 0,
    }

    result = send_message(
        config,
        "文件传输助手",
        "hello",
        search_func=lambda target, cfg: calls.append(f"search:{target}") or True,
        paste_func=lambda message: calls.append(f"paste:{message}") or True,
        enter_func=lambda: calls.append("enter") or True,
        screenshot_func=lambda cfg: calls.append("screenshot") or "screen.png",
        screen_state_func=lambda path: calls.append(f"state:{path}")
        or ScreenStateDetection(ScreenState.INPUT_READY, 0.9, path, "input ready"),
    )

    assert result is True
    assert calls == [
        "screenshot",
        "state:screen.png",
        "search:文件传输助手",
        "paste:hello",
        "enter",
        "screenshot",
    ]
    with connect_database(database_path) as connection:
        events = list_audit_events(connection)
    assert events[-1]["event_type"] == "real_send_success"


def test_message_sender_captures_screenshot_on_real_search_failure() -> None:
    calls: list[str] = []
    config = {
        "dry_run": False,
        "allow_real_send": True,
        "require_known_screen_state_for_real_send": False,
        "max_retry": 2,
        "send_delay_seconds": 0,
    }

    result = send_message(
        config,
        "文件传输助手",
        "hello",
        search_func=lambda target, cfg: UiActionResult("search_contact", False, "search failed"),
        paste_func=lambda message: calls.append("paste") or True,
        enter_func=lambda: calls.append("enter") or True,
        screenshot_func=lambda cfg: calls.append("screenshot") or "failure.png",
    )

    assert result is False
    assert calls == ["screenshot", "screenshot"]


def test_message_sender_does_not_delegate_retry_to_search() -> None:
    search_retry_values: list[int] = []
    config = {
        "dry_run": False,
        "allow_real_send": True,
        "require_known_screen_state_for_real_send": False,
        "max_retry": 5,
        "send_delay_seconds": 0,
    }

    result = send_message(
        config,
        "文件传输助手",
        "hello",
        search_func=lambda target, cfg: search_retry_values.append(cfg["max_retry"]) or False,
        screenshot_func=lambda cfg: "failure.png",
    )

    assert result is False
    assert search_retry_values == [1, 1, 1, 1, 1]


def test_message_sender_blocks_real_send_when_screen_state_unknown() -> None:
    calls: list[str] = []
    config = {
        "dry_run": False,
        "allow_real_send": True,
        "require_known_screen_state_for_real_send": True,
        "max_retry": 1,
        "send_delay_seconds": 0,
    }

    result = send_message(
        config,
        "文件传输助手",
        "hello",
        search_func=lambda target, cfg: calls.append("search") or True,
        paste_func=lambda message: calls.append("paste") or True,
        enter_func=lambda: calls.append("enter") or True,
        screenshot_func=lambda cfg: calls.append("screenshot") or "screen.png",
    )

    assert result is False
    assert calls == ["screenshot"]


def test_birthday_matches_mm_dd() -> None:
    assert birthday_matches(date(2026, 7, 5), "07-05") is True
    assert birthday_matches(date(2026, 7, 5), "07-06") is False


def test_birthday_matches_yyyy_mm_dd() -> None:
    assert birthday_matches(date(2026, 7, 5), "2000-07-05") is True
    assert birthday_matches(date(2026, 7, 5), "2000-07-06") is False
