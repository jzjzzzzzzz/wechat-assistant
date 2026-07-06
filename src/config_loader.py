"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.auto_reply_policy import DEFAULT_AUTO_REPLY_CONFIG, validate_auto_reply_config


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
    "database_path": "data/wechat_assistant.sqlite3",
    "audit_enabled": True,
    "ocr_engine": "easyocr",
    "ocr_confidence_threshold": 0.3,
    "search_delay_seconds": 1.5,
    "send_delay_seconds": 1.0,
    "ui_action_interval_seconds": 0.2,
    "require_known_screen_state_for_real_send": True,
    "vision_template_threshold": 0.85,
    "max_retry": 3,
    "auto_reply": DEFAULT_AUTO_REPLY_CONFIG.copy(),
    "background_scan": {
        "enabled": True,
        "prefer_background_capture": True,
        "allow_activate_wechat_fallback": False,
        "require_screenshot_verification": True,
        "verifier_min_confidence": 0.70,
        "debug_screenshot_dir": "screenshots/background_scan",
        "max_scan_interval_seconds": 30,
    },
}

REQUIRED_TYPES: dict[str, type | tuple[type, ...]] = {
    "dry_run": bool,
    "allow_real_send": bool,
    "test_contact": str,
    "test_message": str,
    "wechat_app_name": str,
    "screenshot_dir": str,
    "log_file": str,
    "database_path": str,
    "audit_enabled": bool,
    "ocr_engine": str,
    "ocr_confidence_threshold": (int, float),
    "search_delay_seconds": (int, float),
    "send_delay_seconds": (int, float),
    "ui_action_interval_seconds": (int, float),
    "require_known_screen_state_for_real_send": bool,
    "vision_template_threshold": (int, float),
    "max_retry": int,
    "auto_reply": dict,
    "background_scan": dict,
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
    validated["ui_action_interval_seconds"] = float(validated["ui_action_interval_seconds"])
    validated["ocr_confidence_threshold"] = float(validated["ocr_confidence_threshold"])
    validated["vision_template_threshold"] = float(validated["vision_template_threshold"])
    if not 0.0 <= validated["ocr_confidence_threshold"] <= 1.0:
        raise ConfigError("Invalid config key 'ocr_confidence_threshold': must be between 0 and 1")
    if not 0.0 <= validated["vision_template_threshold"] <= 1.0:
        raise ConfigError("Invalid config key 'vision_template_threshold': must be between 0 and 1")
    if validated["max_retry"] < 1:
        raise ConfigError("Invalid config key 'max_retry': must be >= 1")
    try:
        validated["auto_reply"] = validate_auto_reply_config(validated)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    background_defaults = DEFAULT_SETTINGS["background_scan"].copy()
    background_raw = validated.get("background_scan", {})
    background_defaults.update(background_raw)
    validated["background_scan"] = background_defaults
    if not isinstance(validated["background_scan"].get("enabled"), bool):
        raise ConfigError("Invalid config key 'background_scan.enabled': expected bool")
    if not isinstance(validated["background_scan"].get("prefer_background_capture"), bool):
        raise ConfigError("Invalid config key 'background_scan.prefer_background_capture': expected bool")
    if not isinstance(validated["background_scan"].get("allow_activate_wechat_fallback"), bool):
        raise ConfigError("Invalid config key 'background_scan.allow_activate_wechat_fallback': expected bool")
    if not isinstance(validated["background_scan"].get("require_screenshot_verification"), bool):
        raise ConfigError("Invalid config key 'background_scan.require_screenshot_verification': expected bool")
    validated["background_scan"]["verifier_min_confidence"] = float(
        validated["background_scan"]["verifier_min_confidence"]
    )
    validated["background_scan"]["max_scan_interval_seconds"] = float(
        validated["background_scan"]["max_scan_interval_seconds"]
    )
    if not 0.0 <= validated["background_scan"]["verifier_min_confidence"] <= 1.0:
        raise ConfigError("Invalid config key 'background_scan.verifier_min_confidence': must be between 0 and 1")
    if validated["background_scan"]["max_scan_interval_seconds"] <= 0:
        raise ConfigError("Invalid config key 'background_scan.max_scan_interval_seconds': must be > 0")
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
