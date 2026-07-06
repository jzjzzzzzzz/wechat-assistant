from pathlib import Path

import yaml

from src.config_loader import DEFAULT_SETTINGS, load_config


def test_load_config_reads_settings_file(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        yaml.safe_dump(DEFAULT_SETTINGS, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["test_contact"] == "文件传输助手"
    assert config["test_message"] == "WeChat Assistant test message"


def test_default_dry_run_is_true() -> None:
    config = load_config()

    assert config["dry_run"] is True


def test_default_allow_real_send_is_false() -> None:
    config = load_config()

    assert config["allow_real_send"] is False


def test_default_owner_status_is_online_and_scroll_disabled() -> None:
    config = load_config()

    assert config["owner"]["status_default"] == "online"
    assert config["owner"]["offline_reply_immediate"] is True
    assert config["unread_scan"]["enable_scroll_scan"] is False


def test_default_auto_reply_requires_private_chat_whitelist_with_test_user() -> None:
    config = load_config()

    assert config["auto_reply"]["require_private_chat_whitelist"] is True
    assert "爱" in config["auto_reply"]["private_chat_whitelist"]
