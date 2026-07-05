from pathlib import Path

import yaml

from src.config_loader import DEFAULT_SETTINGS, load_config
from src.gui.settings import dangerous_changes, parse_bool, save_settings


def _write_settings(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(DEFAULT_SETTINGS, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_parse_bool_accepts_common_values() -> None:
    assert parse_bool("true") is True
    assert parse_bool("off") is False


def test_save_settings_allows_safe_change(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    _write_settings(settings_path)

    result = save_settings({"test_message": "updated"}, path=settings_path)

    assert result.ok is True
    assert load_config(settings_path)["test_message"] == "updated"


def test_save_settings_blocks_dangerous_change_without_confirmation(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    _write_settings(settings_path)

    result = save_settings({"dry_run": "false"}, path=settings_path, confirm_dangerous=False)

    assert result.ok is False
    assert "requires confirmation" in result.message
    assert load_config(settings_path)["dry_run"] is True


def test_save_settings_allows_dangerous_change_with_confirmation(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    _write_settings(settings_path)

    result = save_settings({"dry_run": "false"}, path=settings_path, confirm_dangerous=True)

    assert result.ok is True
    assert load_config(settings_path)["dry_run"] is False


def test_save_settings_rejects_invalid_type(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    _write_settings(settings_path)

    result = save_settings({"max_retry": "not-a-number"}, path=settings_path)

    assert result.ok is False
    assert "Invalid settings" in result.message


def test_dangerous_changes_detects_allow_real_send_enable() -> None:
    changes = dangerous_changes(
        {"dry_run": True, "allow_real_send": False},
        {"dry_run": True, "allow_real_send": True},
    )

    assert changes == ["allow_real_send"]
