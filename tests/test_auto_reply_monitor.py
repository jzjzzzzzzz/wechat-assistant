import json
import logging
from datetime import datetime

from src.auto_reply_monitor import AutoReplyMonitor, MonitorRunSummary
from src.auto_reply_policy import AutoReplyEvent
from src.auto_reply_state import AutoReplyStateStore
from src.main import run_command


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


def make_config(tmp_path, owner_status_default="offline"):
    return {
        "dry_run": True,
        "allow_real_send": False,
        "log_file": str(tmp_path / "app.log"),
        "database_path": str(tmp_path / "wechat_assistant.sqlite3"),
        "wechat_app_name": "WeChat",
        "owner": {
            "status_default": owner_status_default,
            "offline_reply_immediate": True,
            "status_menu_enabled": True,
        },
        "auto_reply": {
            "enabled": False,
            "dry_run": True,
            "delay_minutes": 5,
            "poll_interval_seconds": 5,
            "cooldown_minutes": 60,
            "state_stale_minutes": 1440,
            "private_only": True,
            "reply_message": "号主不在线～ AI自动回复的",
            "detection_priority": ["notification_ocr", "unread_chat_scan"],
            "allowed_test_contacts": ["文件传输助手"],
            "require_private_chat_whitelist": True,
            "private_chat_whitelist": ["爱", "Alice"],
            "blocklist_keywords": ["群", "服务通知", "公众号"],
            "non_private_keywords": ["Official Accounts", "Service Accounts", "公众号"],
            "min_ocr_confidence": 0.65,
        },
    }


def make_event(status="ready_for_reply", reason=None):
    return AutoReplyEvent(
        source="unread_chat_scan",
        sender="Alice",
        message_preview="red_unread_badge:1",
        detected_at=BASE_TIME,
        first_seen_at=BASE_TIME,
        last_seen_at=BASE_TIME,
        confidence=0.95,
        status=status,
        reason=reason,
        is_private_candidate=True,
    )


def test_monitor_limited_run_writes_jsonl_and_sqlite_summary(tmp_path):
    events_jsonl = tmp_path / "events.jsonl"
    closed = []
    captured_config = {}

    class FakeStore:
        def close(self):
            closed.append(True)

    class FakeDaemon:
        def __init__(self, config):
            captured_config.update(config)
            self.state_store = FakeStore()

        def run_once(self):
            return [make_event()]

    monitor = AutoReplyMonitor(
        make_config(tmp_path),
        interval_seconds=1,
        minutes=60,
        events_jsonl_path=events_jsonl,
        monitor_log_path=tmp_path / "monitor.log",
        daemon_factory=FakeDaemon,
        sleep_func=lambda seconds: None,
        logger=logging.getLogger("test_monitor_limited_run"),
    )

    summary = monitor.run(max_passes=1)

    assert summary.total_passes == 1
    assert summary.candidates_detected == 1
    assert summary.ready_for_reply_count == 1
    assert summary.would_auto_reply_count == 1
    assert captured_config["dry_run"] is True
    assert captured_config["allow_real_send"] is False
    assert closed == [True]

    lines = events_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["type"] == "monitor_pass"
    assert payload["would_auto_reply_count"] == 1

    with AutoReplyStateStore(make_config(tmp_path)["database_path"]) as store:
        row = store.connection.execute(
            "SELECT metadata_json FROM audit_events WHERE event_type = 'auto_reply_monitor_summary'"
        ).fetchone()
    assert row is not None
    metadata = json.loads(row["metadata_json"])
    assert metadata["total_passes"] == 1


def test_auto_reply_state_list_cli_prints_rows(monkeypatch, tmp_path, capsys):
    config = make_config(tmp_path)
    with AutoReplyStateStore(config["database_path"]) as store:
        store.upsert_event_state(
            make_event(status="pending"),
            now=BASE_TIME,
            cooldown_minutes=60,
            stale_after_minutes=1440,
        )

    monkeypatch.setattr("src.main.load_config", lambda: config)

    result = run_command("auto-reply-state", command_args=["list"])

    output = capsys.readouterr().out
    assert result == 0
    assert "row_count: 1" in output
    assert "sender=Alice" in output
    assert "real_sent=False" in output


def test_auto_reply_monitor_cli_requires_dry_run(tmp_path):
    result = run_command("auto-reply-monitor", dry_run=False, minutes=0)

    assert result == 2


def test_monitor_report_prints_no_summaries(monkeypatch, tmp_path, capsys):
    config = make_config(tmp_path)
    monkeypatch.setattr("src.main.load_config", lambda: config)

    result = run_command("monitor-report")

    output = capsys.readouterr().out
    assert result == 0
    assert "No auto-reply monitor summaries found." in output


def test_print_monitor_summary_shape():
    summary = MonitorRunSummary(
        started_at=BASE_TIME,
        completed_at=BASE_TIME,
        duration_completed_seconds=0.0,
        requested_minutes=0.0,
        interval_seconds=1.0,
        total_passes=0,
        candidates_detected=0,
        pending_count=0,
        ready_for_reply_count=0,
        ignored_count=0,
        would_auto_reply_count=0,
        ignored_reasons={},
        safe_failures=[],
        errors=[],
        monitor_log_path="logs/auto_reply_monitor.log",
        events_jsonl_path="logs/auto_reply_events.jsonl",
        database_path="data/wechat_assistant.sqlite3",
        stopped_by="completed",
    )

    assert summary.as_dict()["total_passes"] == 0
