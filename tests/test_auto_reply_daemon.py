from datetime import datetime, timedelta

from src.auto_reply_daemon import AutoReplyDaemon, print_planned_actions, run_auto_reply_once
from src.auto_reply_policy import AutoReplyEvent
from src.main import run_command


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


def make_event(sender="Alice", first_seen_at=None):
    first_seen_at = first_seen_at or BASE_TIME - timedelta(minutes=5)
    return AutoReplyEvent(
        source="notification_ocr",
        sender=sender,
        message_preview="hello",
        detected_at=BASE_TIME,
        first_seen_at=first_seen_at,
        last_seen_at=BASE_TIME,
        confidence=0.95,
        status="pending",
        is_private_candidate=True,
    )


def make_config(**auto_reply_overrides):
    auto_reply = {
        "enabled": False,
        "dry_run": True,
        "delay_minutes": 5,
        "poll_interval_seconds": 5,
        "cooldown_minutes": 60,
        "private_only": True,
        "reply_message": "号主不在线～ AI自动回复的",
        "detection_priority": ["notification_ocr", "unread_chat_scan"],
        "allowed_test_contacts": ["文件传输助手"],
        "blocklist_keywords": ["群", "服务通知", "公众号"],
        "min_ocr_confidence": 0.65,
    }
    auto_reply.update(auto_reply_overrides)
    return {
        "dry_run": True,
        "allow_real_send": False,
        "log_file": "logs/app.log",
        "wechat_app_name": "WeChat",
        "auto_reply": auto_reply,
    }


def test_run_once_exits_cleanly_and_runs_both_detectors():
    calls = []
    daemon = AutoReplyDaemon(
        make_config(delay_minutes=0),
        notification_detector=lambda config: calls.append("notification") or [make_event()],
        unread_scanner=lambda config: calls.append("unread") or [],
        now_func=lambda: BASE_TIME,
    )

    events = daemon.run_once()

    assert calls == ["notification", "unread"]
    assert len(events) == 1
    assert events[0].status == "ready_for_reply"


def test_dry_run_never_calls_real_sender():
    sender_calls = []

    events = run_auto_reply_once(
        make_config(delay_minutes=0),
        notification_detector=lambda config: [make_event()],
        unread_scanner=lambda config: [],
    )

    assert events[0].status == "ready_for_reply"
    assert sender_calls == []


def test_print_planned_actions_outputs_dry_run_text(capsys):
    event = make_event()
    event = AutoReplyDaemon(
        make_config(delay_minutes=0),
        notification_detector=lambda config: [event],
        unread_scanner=lambda config: [],
        now_func=lambda: BASE_TIME,
    ).run_once()[0]

    print_planned_actions([event], make_config())

    output = capsys.readouterr().out
    assert "WOULD AUTO REPLY" in output
    assert "Target: Alice" in output
    assert "Message: 号主不在线～ AI自动回复的" in output


def test_cli_auto_reply_daemon_once_exits_cleanly(monkeypatch):
    class FakeDaemon:
        def __init__(self, config):
            self.config = config

        def run_once(self):
            return []

    monkeypatch.setattr("src.auto_reply_daemon.AutoReplyDaemon", FakeDaemon)

    result = run_command("auto-reply-daemon", dry_run=True, once=True)

    assert result == 0


def test_cli_auto_reply_daemon_requires_dry_run():
    result = run_command("auto-reply-daemon", dry_run=False, once=True)

    assert result == 2
