"""WeChat for Mac window control helpers."""

from __future__ import annotations

import logging
import subprocess
import time
from typing import Any


LOGGER = logging.getLogger(__name__)


def _import_pyautogui():
    try:
        import pyautogui  # type: ignore

        return pyautogui, None
    except Exception as exc:  # pragma: no cover - depends on local install
        return None, exc


def is_wechat_running(app_name: str = "WeChat") -> bool:
    script = f'tell application "System Events" to (name of processes) contains "{app_name}"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        running = result.stdout.strip().lower() == "true"
        LOGGER.info("WeChat running check for %s: %s", app_name, running)
        return running
    except Exception as exc:
        LOGGER.error("Failed to check WeChat process: %s", exc)
        return False


def open_wechat(app_name: str = "WeChat") -> bool:
    if is_wechat_running(app_name):
        return True

    LOGGER.info("WeChat is not running. Opening with macOS open -a %s", app_name)
    try:
        subprocess.run(["open", "-a", app_name], check=False)
        return True
    except Exception as exc:
        LOGGER.error("Failed to open WeChat app %s: %s", app_name, exc)
        return False


def activate_wechat(app_name: str = "WeChat", wait_seconds: float = 2.0) -> bool:
    if not open_wechat(app_name):
        return False

    script = f'tell application "{app_name}" to activate'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            LOGGER.error("Failed to activate WeChat: %s", result.stderr.strip())
            return False
        LOGGER.info("Activated WeChat window.")
        time.sleep(wait_seconds)
        return True
    except Exception as exc:
        LOGGER.error("Failed to activate WeChat: %s", exc)
        return False


def search_contact(contact_name: str, config: dict[str, Any]) -> bool:
    app_name = config.get("wechat_app_name", "WeChat")
    if not activate_wechat(app_name, wait_seconds=float(config.get("search_delay_seconds", 1.5))):
        return False

    pyautogui, import_error = _import_pyautogui()
    if import_error:
        LOGGER.error("pyautogui import failed: %s", import_error)
        return False

    try:
        import pyperclip  # type: ignore

        LOGGER.info("Searching WeChat contact by shortcut: %s", contact_name)
        pyautogui.hotkey("command", "f")
        time.sleep(0.2)
        pyautogui.hotkey("command", "a")
        pyperclip.copy(contact_name)
        pyautogui.hotkey("command", "v")
        time.sleep(float(config.get("search_delay_seconds", 1.5)))
        pyautogui.press("enter")
        time.sleep(float(config.get("search_delay_seconds", 1.5)))
        LOGGER.info("Entered chat for contact search target: %s", contact_name)
        return True
    except Exception as exc:
        LOGGER.error("Failed to search WeChat contact %s: %s", contact_name, exc)
        return False
