"""Settings editor support for the Tkinter GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.config_loader import DEFAULT_CONFIG_PATH, ConfigError, load_config, validate_config


DANGEROUS_SETTING_MESSAGES = {
    "dry_run": "Changing dry_run to false can allow real UI actions.",
    "allow_real_send": "Changing allow_real_send to true can allow real sending when other gates pass.",
}


@dataclass(frozen=True)
class SettingsSaveResult:
    ok: bool
    message: str
    config: dict[str, Any] | None = None


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value: {value}")


def coerce_settings(raw_settings: dict[str, Any], base_config: dict[str, Any]) -> dict[str, Any]:
    coerced = base_config.copy()
    for key, value in raw_settings.items():
        if key in {"dry_run", "allow_real_send", "audit_enabled", "require_known_screen_state_for_real_send"}:
            coerced[key] = parse_bool(value)
        elif key in {
            "search_delay_seconds",
            "send_delay_seconds",
            "ui_action_interval_seconds",
            "ocr_confidence_threshold",
            "vision_template_threshold",
        }:
            coerced[key] = float(value)
        elif key == "max_retry":
            coerced[key] = int(value)
        else:
            coerced[key] = value
    return validate_config(coerced)


def dangerous_changes(current_config: dict[str, Any], new_config: dict[str, Any]) -> list[str]:
    changes: list[str] = []
    if current_config.get("dry_run", True) is True and new_config.get("dry_run") is False:
        changes.append("dry_run")
    if current_config.get("allow_real_send", False) is False and new_config.get("allow_real_send") is True:
        changes.append("allow_real_send")
    return changes


def save_settings(
    raw_settings: dict[str, Any],
    *,
    path: str | Path = DEFAULT_CONFIG_PATH,
    confirm_dangerous: bool = False,
) -> SettingsSaveResult:
    settings_path = Path(path)
    current_config = load_config(settings_path)
    try:
        new_config = coerce_settings(raw_settings, current_config)
    except Exception as exc:
        return SettingsSaveResult(False, f"Invalid settings: {exc}")

    dangerous = dangerous_changes(current_config, new_config)
    if dangerous and not confirm_dangerous:
        messages = [DANGEROUS_SETTING_MESSAGES[key] for key in dangerous]
        return SettingsSaveResult(False, "Dangerous setting change requires confirmation: " + " ".join(messages))

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with settings_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(new_config, file, allow_unicode=True, sort_keys=False)
    return SettingsSaveResult(True, "Settings saved", new_config)


def run_settings_window(config_path: str | Path = DEFAULT_CONFIG_PATH) -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    current_config = load_config(config_path)
    editable_keys = [
        "dry_run",
        "allow_real_send",
        "test_contact",
        "test_message",
        "search_delay_seconds",
        "send_delay_seconds",
        "max_retry",
    ]

    window = tk.Toplevel()
    window.title("Settings")
    window.geometry("520x360")
    window.minsize(480, 320)

    frame = ttk.Frame(window, padding=16)
    frame.pack(fill="both", expand=True)

    values: dict[str, tk.StringVar] = {}
    for row, key in enumerate(editable_keys):
        ttk.Label(frame, text=key).grid(row=row, column=0, sticky="w", pady=4)
        values[key] = tk.StringVar(value=str(current_config.get(key, "")))
        ttk.Entry(frame, textvariable=values[key], width=42).grid(row=row, column=1, sticky="ew", pady=4)

    confirm_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="Confirm dangerous send-related setting changes", variable=confirm_var).grid(
        row=len(editable_keys), column=0, columnspan=2, sticky="w", pady=(12, 4)
    )

    status = tk.StringVar(value="Edit settings and save.")
    ttk.Label(frame, textvariable=status, wraplength=460).grid(
        row=len(editable_keys) + 1, column=0, columnspan=2, sticky="w", pady=(8, 8)
    )

    def on_save() -> None:
        raw = {key: var.get() for key, var in values.items()}
        result = save_settings(raw, path=config_path, confirm_dangerous=confirm_var.get())
        status.set(result.message)
        if result.ok:
            messagebox.showinfo("Settings", result.message)
        else:
            messagebox.showwarning("Settings", result.message)

    ttk.Button(frame, text="Save", command=on_save).grid(row=len(editable_keys) + 2, column=0, sticky="w")
    ttk.Button(frame, text="Cancel", command=window.destroy).grid(row=len(editable_keys) + 2, column=1, sticky="e")
    frame.columnconfigure(1, weight=1)
