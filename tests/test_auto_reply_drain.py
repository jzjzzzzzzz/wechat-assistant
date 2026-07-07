from datetime import datetime

from src.auto_reply_drain import AutoReplyDrainSummary, run_auto_reply_drain
from src.auto_reply_policy import AutoReplyEvent
from src.dock_unread_detector import DockUnreadDetection
from src.main import run_command


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


def make_config(*, real: bool = True):
    return {
        "dry_run": not real,
        "allow_real_send": real,
        "log_file": "logs/app.log",
        "database_path": "data/test.sqlite3",
        "wechat_app_name": "WeChat",
        "owner": {"status_default": "offline", "offline_reply_immediate": True},
        "auto_reply": {
            "dry_run": not real,
            "delay_minutes": 5,
            "poll_interval_seconds": 5,
            "cooldown_minutes": 60,
            "state_stale_minutes": 1440,
            "private_only": True,
            "reply_message": "号主不在线～ AI自动回复的",
            "detection_priority": ["notification_ocr", "unread_chat_scan"],
            "require_private_chat_whitelist": True,
            "private_chat_whitelist": ["爱"],
            "blocklist_keywords": ["群", "服务通知"],
            "non_private_keywords": ["公众号", "服务通知"],
            "min_ocr_confidence": 0.65,
        },
        "unread_scan": {
            "enable_scroll_scan": False,
            "restore_position_after_scan": True,
            "stop_on_first_private_candidate": True,
        },
        "dock_unread": {"enabled": True, "require_for_auto_reply": True},
    }


def make_event(status: str = "ready_for_reply"):
    return AutoReplyEvent(
        source="unread_chat_scan",
        sender="爱",
        message_preview="red_unread_badge:1",
        detected_at=BASE_TIME,
        first_seen_at=BASE_TIME,
        last_seen_at=BASE_TIME,
        confidence=0.9,
        status=status,
        is_private_candidate=True,
    )


def dock_detection(has_unread: bool | None = True):
    return DockUnreadDetection(
        ok=has_unread is not None,
        has_unread=has_unread,
        message="dock fixture",
        confidence=0.9,
        detected_at=BASE_TIME,
    )


def test_drain_enables_scroll_and_stops_when_dock_clears():
    captured = {}
    dock_values = [True, False]

    class FakeStore:
        def close(self):
            captured["store_closed"] = True

    class FakeWatcher:
        def close(self):
            captured["watcher_closed"] = True

    class FakeDaemon:
        def __init__(self, config, *, dry_run_mode=True):
            captured["config"] = config
            captured["dry_run_mode"] = dry_run_mode
            self.state_store = FakeStore()
            self._status_watcher = FakeWatcher()

        def run_once(self):
            return [make_event()]

    def fake_dock(_config):
        return dock_detection(dock_values.pop(0))

    activate_calls = []
    summary = run_auto_reply_drain(
        make_config(real=True),
        max_passes=3,
        interval_seconds=0,
        daemon_factory=FakeDaemon,
        dock_unread_detector=fake_dock,
        activate_func=lambda *args, **kwargs: activate_calls.append((args, kwargs)) or True,
        sleep_func=lambda seconds: None,
    )

    assert summary.total_passes == 1
    assert summary.ready_for_reply_count == 1
    assert summary.stopped_by == "dock_unread_cleared"
    assert summary.final_dock_has_unread is False
    assert captured["dry_run_mode"] is False
    assert captured["config"]["unread_scan"]["enable_scroll_scan"] is True
    assert captured["config"]["unread_scan"]["ensure_wechat_frontmost_for_scroll"] is True
    assert captured["config"]["unread_scan"]["stop_on_first_private_candidate"] is False
    assert captured["store_closed"] is True
    assert captured["watcher_closed"] is True
    assert len(activate_calls) == 1


def test_drain_rejects_dry_run_config():
    try:
        run_auto_reply_drain(make_config(real=False), max_passes=1, interval_seconds=0)
    except ValueError as exc:
        assert "requires real-send mode" in str(exc)
    else:
        raise AssertionError("dry-run config should be rejected")


def test_cli_drain_force_send_switches_to_real_config(monkeypatch, tmp_path):
    captured = {}
    config = make_config(real=False)
    config["database_path"] = str(tmp_path / "wechat_assistant.sqlite3")
    monkeypatch.setattr("src.main.load_config", lambda: config)

    def fake_drain(config, *, max_passes, interval_seconds):
        captured["dry_run"] = config["dry_run"]
        captured["allow_real_send"] = config["allow_real_send"]
        captured["auto_reply_dry_run"] = config["auto_reply"]["dry_run"]
        captured["max_passes"] = max_passes
        return AutoReplyDrainSummary(
            started_at=BASE_TIME,
            completed_at=BASE_TIME,
            total_passes=0,
            max_passes=max_passes,
            interval_seconds=interval_seconds,
            detected_candidate_count=0,
            ready_for_reply_count=0,
            ignored_count=0,
            pending_count=0,
            real_send_candidate_count=0,
            stopped_by="dock_unread_cleared",
            final_dock_has_unread=False,
        )

    monkeypatch.setattr("src.auto_reply_drain.run_auto_reply_drain", fake_drain)

    result = run_command("auto-reply-drain", force_send=True, max_passes=4)

    assert result == 0
    assert captured == {
        "dry_run": False,
        "allow_real_send": True,
        "auto_reply_dry_run": False,
        "max_passes": 4,
    }
