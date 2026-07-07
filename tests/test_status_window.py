from datetime import datetime

import src.status_window as status_window
from src.owner_status import OwnerStatusRecord


BASE_TIME = datetime(2026, 7, 7, 10, 0, 0)


def test_importing_status_window_does_not_start_gui_loop():
    assert hasattr(status_window, "run_status_window")


def test_status_window_text_for_status():
    assert status_window.status_window_text_for_status("online") == "OL"
    assert status_window.status_window_text_for_status("offline") == "OFF"
    assert status_window.status_window_button_title_for_status("online") == "OL"
    assert status_window.status_window_button_title_for_status("offline") == "OFF"
    assert status_window.status_window_lock_button_title(True) == "UNLOCK"
    assert status_window.status_window_lock_button_title(False) == "LOCK"


def test_status_window_options_defaults_and_clamps():
    options = status_window.status_window_options({})
    assert options.width == 220
    assert options.height == 46
    assert options.margin_top == 142
    assert options.refresh_seconds == 1.0
    assert options.locked_on_top is True

    clamped = status_window.status_window_options({
        "owner": {
            "status_window": {
                "width": 999,
                "height": 1,
                "refresh_seconds": 99,
            }
        }
    })
    assert clamped.width == 420
    assert clamped.height == 32
    assert clamped.refresh_seconds == 10.0


def test_status_window_check_exits_without_gui_loop(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(status_window, "get_owner_status", lambda cfg: OwnerStatusRecord(
        "online",
        BASE_TIME,
        "test",
        None,
        "database",
    ))

    result = status_window.status_window_check({"database_path": str(tmp_path / "test.sqlite3")})

    output = capsys.readouterr().out
    assert result in {0, 1}
    assert "expected status button: OL" in output
    assert "refresh_seconds: 1.00" in output
    assert "GUI loop would start:" in output


def test_status_window_disabled_does_not_scan_wechat_or_send(monkeypatch):
    calls = []
    monkeypatch.setattr("src.unread_scanner.scan_unread_events", lambda *args, **kwargs: calls.append("scan"))
    monkeypatch.setattr("src.message_sender.send_message", lambda *args, **kwargs: calls.append("send"))

    result = status_window.run_status_window({"owner": {"status_window_enabled": False}})

    assert result == 2
    assert calls == []
