from datetime import datetime

from src.main import run_command
from src.macos_status_detector import MacosStatusDetection


def make_config(tmp_path):
    return {
        "dry_run": True,
        "allow_real_send": False,
        "log_file": "logs/app.log",
        "database_path": str(tmp_path / "wechat_assistant.sqlite3"),
        "wechat_app_name": "WeChat",
        "owner": {
            "status_default": "online",
            "offline_reply_immediate": True,
            "status_menu_enabled": True,
        },
        "unread_scan": {
            "enable_scroll_scan": False,
            "max_scroll_pages": 5,
            "scroll_amount": -5,
            "scroll_pause_seconds": 0.0,
            "restore_position_after_scan": True,
            "stop_on_first_private_candidate": True,
            "ignore_public_accounts": True,
            "ignore_service_accounts": True,
            "ignore_group_chats": True,
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
            "private_chat_whitelist": ["爱"],
            "blocklist_keywords": ["群", "服务通知", "公众号"],
            "non_private_keywords": ["Official Accounts", "Service Accounts", "公众号"],
            "min_ocr_confidence": 0.65,
        },
    }


def test_owner_status_cli_get_set_toggle(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))

    assert run_command("owner-status") == 0
    assert "status: online" in capsys.readouterr().out

    assert run_command("owner-status", command_args=["set", "offline"]) == 0
    assert "status: offline" in capsys.readouterr().out

    assert run_command("owner-status", command_args=["toggle"]) == 0
    assert "status: online" in capsys.readouterr().out


def test_unread_scan_scroll_cli_override(monkeypatch, tmp_path, capsys):
    captured = {}

    def fake_unread_scan_once(config):
        captured["scroll"] = config["unread_scan"]["enable_scroll_scan"]
        return []

    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))
    monkeypatch.setattr("src.unread_scanner.unread_scan_once", fake_unread_scan_once)
    monkeypatch.setattr("src.unread_scanner.get_last_unread_scan_report", lambda: None)

    assert run_command("unread-scan", once=True) == 0
    assert captured["scroll"] is False
    assert "scroll_scan_enabled: False" in capsys.readouterr().out

    assert run_command("unread-scan", once=True, scroll=True) == 0
    assert captured["scroll"] is True
    assert "scroll_scan_enabled: True" in capsys.readouterr().out


def test_status_menu_check_cli_exits_without_gui_loop(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))
    monkeypatch.setattr("src.status_menu.status_menu_check", lambda config: calls.append("check") or 0)
    monkeypatch.setattr("src.status_menu.run_status_menu", lambda config: calls.append("run") or 0)

    result = run_command("status-menu", check=True)

    assert result == 0
    assert calls == ["check"]


def test_macos_status_check_cli_prints_live_detection_without_side_effects(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))
    monkeypatch.setattr(
        "src.macos_status_detector.detect_macos_status",
        lambda config: MacosStatusDetection(
            raw_status="active",
            db_status="online",
            detected_text="🟢 OL",
            screenshot_path="/tmp/status.png",
            detected_at=datetime(2026, 7, 7, 0, 0, 0),
            confidence=0.9,
        ),
    )

    result = run_command("macos-status-check", once=True)

    output = capsys.readouterr().out
    assert result == 0
    assert "raw_status: active" in output
    assert "db_status: online" in output
    assert "detected_text: 🟢 OL" in output
    assert "safe_to_auto_reply: True" in output


def test_private_whitelist_cli_lists_configured_senders(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))

    result = run_command("private-whitelist", command_args=["list"])

    output = capsys.readouterr().out
    assert result == 0
    assert "require_private_chat_whitelist: True" in output
    assert "count: 1" in output
    assert "- 爱" in output


def test_private_whitelist_cli_add_remove_updates_settings(monkeypatch, tmp_path, capsys):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "\n".join(
            [
                "dry_run: true",
                "allow_real_send: false",
                "auto_reply:",
                "  private_chat_whitelist:",
                "    - \"爱\"",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))
    monkeypatch.setattr("src.private_whitelist.DEFAULT_CONFIG_PATH", settings_path)

    add_result = run_command("private-whitelist", command_args=["add", "Alice"])
    add_output = capsys.readouterr().out
    assert add_result == 0
    assert "action: added" in add_output
    assert "sender: Alice" in add_output

    remove_result = run_command("private-whitelist", command_args=["remove", "Alice"])
    remove_output = capsys.readouterr().out
    assert remove_result == 0
    assert "action: removed" in remove_output


def test_sender_classify_cli_reports_private_sender(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))

    result = run_command("sender-classify", command_args=["爱"])

    output = capsys.readouterr().out
    assert result == 0
    assert "sender: 爱" in output
    assert "is_private: True" in output
    assert "category: private" in output
    assert "matched_whitelist: 爱" in output


def test_sender_classify_cli_reports_group_candidate(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))

    result = run_command("sender-classify", command_args=["项目组(5)"])

    output = capsys.readouterr().out
    assert result == 0
    assert "is_private: False" in output
    assert "category: group_candidate" in output
    assert "member_count_suffix" in output


def test_sender_classify_cli_requires_sender_name(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("src.main.load_config", lambda: make_config(tmp_path))

    result = run_command("sender-classify")

    output = capsys.readouterr().out
    assert result == 2
    assert "Usage: sender-classify" in output
