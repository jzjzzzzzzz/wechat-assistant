from src.main import run_command


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
            "blocklist_keywords": ["群", "服务通知", "公众号"],
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
