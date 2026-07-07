from datetime import datetime, timedelta

from src.auto_reply_daemon import AutoReplyDaemon, print_planned_actions, run_auto_reply_once
from src.auto_reply_policy import AutoReplyEvent
from src.auto_reply_state import AutoReplyStateStore
from src.dock_unread_detector import DockUnreadDetection
from src.macos_status_detector import MacosStatusDetection
from src.main import run_command


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


class FakeStatusWatcher:
    def __init__(self, statuses=None):
        self.statuses = list(statuses or ["offline"])
        self.store = None
        self.closed = False
        self.poll_count = 0

    def poll(self):
        self.poll_count += 1
        status = self.statuses.pop(0) if self.statuses else "offline"
        if status == "online":
            return MacosStatusDetection("active", "online", "OL", None, BASE_TIME, 0.9)
        if status == "offline":
            return MacosStatusDetection("inactive", "offline", "OFF", None, BASE_TIME, 0.9)
        return MacosStatusDetection("unknown", "unknown", "", None, BASE_TIME, 0.0)

    def close(self):
        self.closed = True


class RaisingStatusWatcher:
    store = None

    def poll(self):
        raise AssertionError("screen status watcher should not be called")

    def close(self):
        pass


def make_event(sender="爱", first_seen_at=None):
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


def make_config(tmp_path=None, owner_status_default="online", owner_overrides=None, **auto_reply_overrides):
    auto_reply = {
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
    }
    auto_reply.update(auto_reply_overrides)
    database_path = str((tmp_path / "wechat_assistant.sqlite3") if tmp_path is not None else "data/wechat_assistant.sqlite3")
    return {
        "dry_run": True,
        "allow_real_send": False,
        "log_file": "logs/app.log",
        "wechat_app_name": "WeChat",
        "database_path": database_path,
        "owner": {
            "status_default": owner_status_default,
            "offline_reply_immediate": True,
            "status_menu_enabled": True,
            **(owner_overrides or {}),
        },
        "auto_reply": auto_reply,
    }


def test_run_once_exits_cleanly_and_runs_both_detectors(tmp_path):
    calls = []
    watcher = FakeStatusWatcher(["offline", "offline"])
    daemon = AutoReplyDaemon(
        make_config(tmp_path, delay_minutes=0),
        notification_detector=lambda config: calls.append("notification") or [make_event()],
        unread_scanner=lambda config: calls.append("unread") or [],
        now_func=lambda: BASE_TIME,
        status_watcher=watcher,
    )

    events = daemon.run_once()

    assert calls == ["notification", "unread"]
    assert len(events) == 1
    assert events[0].status == "ready_for_reply"
    assert watcher.poll_count == 2


def test_online_status_detects_but_does_not_prepare_reply(tmp_path):
    calls = []
    daemon = AutoReplyDaemon(
        make_config(tmp_path, owner_status_default="online", delay_minutes=0),
        notification_detector=lambda config: calls.append("notification") or [make_event()],
        unread_scanner=lambda config: calls.append("unread") or [],
        now_func=lambda: BASE_TIME,
        status_watcher=FakeStatusWatcher(["online"]),
    )

    events = daemon.run_once()

    assert calls == ["notification", "unread"]
    assert len(events) == 1
    assert events[0].status == "ignored"
    assert events[0].reason == "owner_online"


def test_unknown_status_blocks_even_when_database_was_online(tmp_path):
    config = make_config(tmp_path, owner_status_default="online", delay_minutes=0)
    store = AutoReplyStateStore(config["database_path"])
    daemon = AutoReplyDaemon(
        config,
        notification_detector=lambda config: [make_event()],
        unread_scanner=lambda config: [],
        now_func=lambda: BASE_TIME,
        state_store=store,
        status_watcher=FakeStatusWatcher(["unknown"]),
    )

    events = daemon.run_once()
    record = store.get("爱", "notification_ocr")
    store.close()

    assert events[0].status == "ignored"
    assert events[0].reason == "system_status_unknown"
    assert record is not None
    assert record.replied_dry_run is False


def test_final_gate_blocks_when_status_changes_to_unknown_before_reply(tmp_path):
    config = make_config(tmp_path, delay_minutes=0)
    store = AutoReplyStateStore(config["database_path"])
    daemon = AutoReplyDaemon(
        config,
        notification_detector=lambda config: [make_event()],
        unread_scanner=lambda config: [],
        now_func=lambda: BASE_TIME,
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline", "unknown"]),
    )

    events = daemon.run_once()
    record = store.get("爱", "notification_ocr")
    store.close()

    assert events[0].status == "ignored"
    assert "system_status_unknown" in (events[0].reason or "")
    assert record is not None
    assert record.replied_dry_run is False


def test_final_gate_blocks_when_status_changes_to_online_before_reply(tmp_path):
    config = make_config(tmp_path, delay_minutes=0)
    store = AutoReplyStateStore(config["database_path"])
    daemon = AutoReplyDaemon(
        config,
        notification_detector=lambda config: [make_event()],
        unread_scanner=lambda config: [],
        now_func=lambda: BASE_TIME,
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline", "online"]),
    )

    events = daemon.run_once()
    record = store.get("爱", "notification_ocr")
    store.close()

    assert events[0].status == "ignored"
    assert "owner_online" in (events[0].reason or "")
    assert record is not None
    assert record.replied_dry_run is False


def test_final_gate_blocks_when_dock_unread_badge_not_confirmed(tmp_path):
    config = make_config(tmp_path, delay_minutes=0)
    config["dock_unread"] = {"enabled": True, "require_for_auto_reply": True}
    store = AutoReplyStateStore(config["database_path"])

    def no_dock_unread(_config):
        return DockUnreadDetection(
            ok=True,
            has_unread=False,
            message="no attached Dock badge",
            confidence=0.7,
            detected_at=BASE_TIME,
        )

    daemon = AutoReplyDaemon(
        config,
        notification_detector=lambda config: [make_event()],
        unread_scanner=lambda config: [],
        now_func=lambda: BASE_TIME,
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline", "offline"]),
        dock_unread_detector=no_dock_unread,
    )

    events = daemon.run_once()
    record = store.get("爱", "notification_ocr")
    store.close()

    assert events[0].status == "ignored"
    assert "dock_unread_not_detected" in (events[0].reason or "")
    assert record is not None
    assert record.replied_dry_run is False


def test_daemon_uses_database_owner_status_when_screen_polling_disabled(tmp_path):
    from src.owner_status import OwnerStatusStore

    config = make_config(tmp_path, delay_minutes=0)
    config["macos_status"] = {"enabled": False}
    with OwnerStatusStore(config["database_path"]) as owner_store:
        owner_store.set_status("offline", updated_by="test", now=BASE_TIME)

    store = AutoReplyStateStore(config["database_path"])
    daemon = AutoReplyDaemon(
        config,
        notification_detector=lambda config: [make_event()],
        unread_scanner=lambda config: [],
        now_func=lambda: BASE_TIME,
        state_store=store,
        status_watcher=RaisingStatusWatcher(),
    )

    events = daemon.run_once()
    record = store.get("爱", "notification_ocr")
    store.close()

    assert events[0].status == "ready_for_reply"
    assert record is not None
    assert record.replied_dry_run is True


def test_dry_run_never_calls_real_sender(tmp_path, monkeypatch):
    sender_calls = []
    monkeypatch.setattr("src.message_sender.send_message", lambda *args, **kwargs: sender_calls.append("send"))

    events = run_auto_reply_once(
        make_config(tmp_path, delay_minutes=0),
        notification_detector=lambda config: [make_event()],
        unread_scanner=lambda config: [],
        status_watcher=FakeStatusWatcher(["offline", "offline"]),
    )

    assert events[0].status == "ready_for_reply"
    assert sender_calls == []


def test_print_planned_actions_outputs_dry_run_text(tmp_path, capsys):
    event = make_event()
    event = AutoReplyDaemon(
        make_config(tmp_path, delay_minutes=0),
        notification_detector=lambda config: [event],
        unread_scanner=lambda config: [],
        now_func=lambda: BASE_TIME,
        status_watcher=FakeStatusWatcher(["offline", "offline"]),
    ).run_once()[0]

    print_planned_actions([event], make_config(tmp_path))

    output = capsys.readouterr().out
    assert "WOULD AUTO REPLY" in output
    assert "Target: 爱" in output
    assert "Message: 号主不在线～ AI自动回复的" in output


def test_cli_auto_reply_daemon_once_exits_cleanly(monkeypatch, tmp_path):
    class FakeDaemon:
        def __init__(self, config, **kwargs):
            self.config = config

        def run_once(self):
            return []

    monkeypatch.setattr("src.auto_reply_daemon.AutoReplyDaemon", FakeDaemon)
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))

    result = run_command("auto-reply-daemon", dry_run=True, once=True)

    assert result == 0


def test_cli_auto_reply_daemon_uses_config_dry_run_by_default(monkeypatch, tmp_path):
    captured = {}

    class FakeDaemon:
        def __init__(self, config, **kwargs):
            captured["dry_run_mode"] = kwargs.get("dry_run_mode")
            self.config = config

        def run_once(self):
            return []

    monkeypatch.setattr("src.auto_reply_daemon.AutoReplyDaemon", FakeDaemon)
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))

    result = run_command("auto-reply-daemon", dry_run=False, once=True)

    assert result == 0
    assert captured["dry_run_mode"] is True


def test_persistent_first_seen_does_not_reset_before_delay(tmp_path):
    config = make_config(tmp_path, owner_overrides={"offline_reply_immediate": False}, delay_minutes=5)
    store = AutoReplyStateStore(config["database_path"])
    detector = lambda cfg: [make_event(first_seen_at=BASE_TIME)]

    daemon = AutoReplyDaemon(
        config,
        notification_detector=detector,
        unread_scanner=lambda cfg: [],
        now_func=lambda: BASE_TIME,
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline"]),
    )
    first_pass = daemon.run_once()

    second_daemon = AutoReplyDaemon(
        config,
        notification_detector=detector,
        unread_scanner=lambda cfg: [],
        now_func=lambda: BASE_TIME + timedelta(minutes=4),
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline"]),
    )
    second_pass = second_daemon.run_once()
    record = store.get("爱", "notification_ocr")
    store.close()

    assert first_pass[0].status == "pending"
    assert second_pass[0].status == "pending"
    assert record is not None
    assert record.first_seen_at == BASE_TIME


def test_candidate_becomes_ready_after_delay_and_marks_dry_run_replied(tmp_path):
    config = make_config(tmp_path, owner_overrides={"offline_reply_immediate": False}, delay_minutes=5)
    store = AutoReplyStateStore(config["database_path"])
    detector = lambda cfg: [make_event(first_seen_at=BASE_TIME - timedelta(minutes=5))]

    daemon = AutoReplyDaemon(
        config,
        notification_detector=detector,
        unread_scanner=lambda cfg: [],
        now_func=lambda: BASE_TIME,
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline", "offline"]),
    )
    events = daemon.run_once()
    record = store.get("爱", "notification_ocr")
    store.close()

    assert events[0].status == "ready_for_reply"
    assert events[0].reason is None
    assert record is not None
    assert record.replied_dry_run is True
    assert record.dry_run_replied_at == BASE_TIME


def test_pending_candidate_remains_pending_before_delay(tmp_path):
    config = make_config(tmp_path, owner_overrides={"offline_reply_immediate": False}, delay_minutes=5)
    store = AutoReplyStateStore(config["database_path"])
    detector = lambda cfg: [make_event(first_seen_at=BASE_TIME)]

    daemon = AutoReplyDaemon(
        config,
        notification_detector=detector,
        unread_scanner=lambda cfg: [],
        now_func=lambda: BASE_TIME + timedelta(minutes=2),
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline"]),
    )
    events = daemon.run_once()
    store.close()

    assert events[0].status == "pending"
    assert events[0].reason == "waiting for owner response window"


def test_cooldown_prevents_repeated_dry_run_reply(tmp_path):
    config = make_config(tmp_path, delay_minutes=0, cooldown_minutes=60)
    store = AutoReplyStateStore(config["database_path"])
    detector = lambda cfg: [make_event(first_seen_at=BASE_TIME - timedelta(minutes=5))]

    first_daemon = AutoReplyDaemon(
        config,
        notification_detector=detector,
        unread_scanner=lambda cfg: [],
        now_func=lambda: BASE_TIME,
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline", "offline"]),
    )
    first_events = first_daemon.run_once()

    second_daemon = AutoReplyDaemon(
        config,
        notification_detector=detector,
        unread_scanner=lambda cfg: [],
        now_func=lambda: BASE_TIME + timedelta(minutes=10),
        state_store=store,
        status_watcher=FakeStatusWatcher(["offline"]),
    )
    second_events = second_daemon.run_once()
    store.close()

    assert first_events[0].status == "ready_for_reply"
    assert second_events[0].status == "ignored"
    assert second_events[0].reason == "cooldown active for sender"


def test_delay_override_sets_cli_config_only(monkeypatch, tmp_path):
    captured = {}

    class FakeDaemon:
        def __init__(self, config, **kwargs):
            captured["delay_minutes"] = config["auto_reply"]["delay_minutes"]
            self.config = config
            self.state_store = AutoReplyStateStore(config["database_path"])

        def run_once(self):
            return []

    monkeypatch.setattr("src.auto_reply_daemon.AutoReplyDaemon", FakeDaemon)
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))

    result = run_command("auto-reply-daemon", dry_run=True, once=True, delay_minutes=0)

    assert result == 0
    assert captured["delay_minutes"] == 0.0
