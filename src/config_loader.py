"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"

DEFAULT_SETTINGS: dict[str, Any] = {
    "dry_run": True,
    "allow_real_send": False,
    "test_contact": "文件传输助手",
    "test_message": "WeChat Assistant test message",
    "wechat_app_name": "WeChat",
    "screenshot_dir": "screenshots",
    "log_file": "logs/app.log",
    "ocr_engine": "easyocr",
    "search_delay_seconds": 1.5,
    "send_delay_seconds": 1.0,
    "max_retry": 3,
}

REQUIRED_TYPES: dict[str, type | tuple[type, ...]] = {
    "dry_run": bool,
    "allow_real_send": bool,
    "test_contact": str,
    "test_message": str,
    "wechat_app_name": str,
    "screenshot_dir": str,
    "log_file": str,
    "ocr_engine": str,
    "search_delay_seconds": (int, float),
    "send_delay_seconds": (int, float),
    "max_retry": int,
}


class ConfigError(ValueError):
    """Raised when configuration is missing required keys or has wrong types."""


def create_default_config(path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(DEFAULT_SETTINGS, file, allow_unicode=True, sort_keys=False)


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    validated = DEFAULT_SETTINGS.copy()
    validated.update(config)

    for key, expected_type in REQUIRED_TYPES.items():
        value = validated.get(key)
        if not isinstance(value, expected_type):
            expected_name = (
                " or ".join(t.__name__ for t in expected_type)
                if isinstance(expected_type, tuple)
                else expected_type.__name__
            )
            raise ConfigError(
                f"Invalid config key '{key}': expected {expected_name}, got {type(value).__name__}"
            )

    validated["search_delay_seconds"] = float(validated["search_delay_seconds"])
    validated["send_delay_seconds"] = float(validated["send_delay_seconds"])
    if validated["max_retry"] < 1:
        raise ConfigError("Invalid config key 'max_retry': must be >= 1")
    return validated


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        create_default_config(config_path)

    with config_path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file) or {}

    if not isinstance(raw_config, dict):
        raise ConfigError("settings.yaml must contain a YAML mapping")
    return validate_config(raw_config)
