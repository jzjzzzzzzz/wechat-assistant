"""WeChat for Mac window control helpers."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Any


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class UiActionResult:
    action: str
    ok: bool
    message: str
    attempt: int = 1
    screenshot_path: str | None = None
    error: str | None = None

    def __bool__(self) -> bool:
        return self.ok


def _import_pyautogui():
    try:
        import pyautogui  # type: ignore

        return pyautogui, None
    except Exception as exc:  # pragma: no cover - depends on local install
        return None, exc


def is_wechat_running_result(app_name: str = "WeChat") -> UiActionResult:
    script = f'tell application "System Events" to (name of processes) contains "{app_name}"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        running = result.stdout.strip().lower() == "true"
        message = f"WeChat running check for {app_name}: {running}"
        LOGGER.info(message)
        return UiActionResult("is_wechat_running", running, message)
    except Exception as exc:
        message = f"Failed to check WeChat process: {exc}"
        LOGGER.error(message)
        return UiActionResult("is_wechat_running", False, message, error=str(exc))


def is_wechat_running(app_name: str = "WeChat") -> bool:
    return is_wechat_running_result(app_name).ok


def open_wechat_result(app_name: str = "WeChat") -> UiActionResult:
    running_result = is_wechat_running_result(app_name)
    if running_result.ok:
        return UiActionResult("open_wechat", True, f"{app_name} is already running.")

    LOGGER.info("WeChat is not running. Opening with macOS open -a %s", app_name)
    try:
        result = subprocess.run(["open", "-a", app_name], check=False, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            message = f"Failed to open WeChat app {app_name}: {stderr or 'open command failed'}"
            LOGGER.error(message)
            return UiActionResult("open_wechat", False, message, error=stderr)
        message = f"Open command issued for {app_name}."
        LOGGER.info(message)
        return UiActionResult("open_wechat", True, message)
    except Exception as exc:
        message = f"Failed to open WeChat app {app_name}: {exc}"
        LOGGER.error(message)
        return UiActionResult("open_wechat", False, message, error=str(exc))


def open_wechat(app_name: str = "WeChat") -> bool:
    return open_wechat_result(app_name).ok


def activate_wechat_result(
    app_name: str = "WeChat",
    wait_seconds: float = 2.0,
    retry_count: int = 1,
) -> UiActionResult:
    retry_count = max(1, int(retry_count))

    script = f'tell application "{app_name}" to activate'
    last_result = UiActionResult("activate_wechat", False, "Activation did not run.")
    for attempt in range(1, retry_count + 1):
        open_result = open_wechat_result(app_name)
        if not open_result.ok:
            last_result = UiActionResult(
                "activate_wechat",
                False,
                f"Cannot activate {app_name}; open step failed: {open_result.message}",
                attempt=attempt,
                error=open_result.error,
            )
            LOGGER.error(last_result.message)
        else:
            try:
                result = subprocess.run(
                    ["osascript", "-e", script],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    message = f"Activated WeChat window on attempt {attempt}."
                    LOGGER.info(message)
                    time.sleep(wait_seconds)
                    return UiActionResult("activate_wechat", True, message, attempt=attempt)
                stderr = result.stderr.strip()
                last_result = UiActionResult(
                    "activate_wechat",
                    False,
                    f"Failed to activate WeChat on attempt {attempt}: {stderr}",
                    attempt=attempt,
                    error=stderr,
                )
                LOGGER.error(last_result.message)
            except Exception as exc:
                last_result = UiActionResult(
                    "activate_wechat",
                    False,
                    f"Failed to activate WeChat on attempt {attempt}: {exc}",
                    attempt=attempt,
                    error=str(exc),
                )
                LOGGER.error(last_result.message)

        if attempt < retry_count:
            time.sleep(wait_seconds)

    return last_result


def activate_wechat(app_name: str = "WeChat", wait_seconds: float = 2.0) -> bool:
    return activate_wechat_result(app_name, wait_seconds=wait_seconds).ok


def search_contact_result(
    contact_name: str,
    config: dict[str, Any],
    *,
    screenshot_func: Any | None = None,
) -> UiActionResult:
    app_name = config.get("wechat_app_name", "WeChat")
    delay = float(config.get("search_delay_seconds", 1.5))
    retry_count = int(config.get("max_retry", 3))
    interval = float(config.get("ui_action_interval_seconds", 0.2))

    pyautogui, import_error = _import_pyautogui()
    if import_error:
        message = f"pyautogui import failed: {import_error}"
        LOGGER.error(message)
        return UiActionResult("search_contact", False, message, error=str(import_error))

    try:
        import pyperclip  # type: ignore
    except Exception as exc:
        message = f"pyperclip import failed: {exc}"
        LOGGER.error(message)
        return UiActionResult("search_contact", False, message, error=str(exc))

    last_result = UiActionResult("search_contact", False, "Search did not run.")
    for attempt in range(1, retry_count + 1):
        activation = activate_wechat_result(app_name, wait_seconds=delay, retry_count=1)
        if not activation.ok:
            screenshot_path = screenshot_func(config) if screenshot_func else None
            last_result = UiActionResult(
                "search_contact",
                False,
                f"WeChat activation failed before contact search: {activation.message}",
                attempt=attempt,
                screenshot_path=screenshot_path,
                error=activation.error,
            )
            LOGGER.error(last_result.message)
        else:
            try:
                LOGGER.info(
                    "Searching WeChat contact by shortcuts. target=%s attempt=%s/%s",
                    contact_name,
                    attempt,
                    retry_count,
                )
                pyautogui.hotkey("command", "f")
                time.sleep(interval)
                pyautogui.hotkey("command", "a")
                pyperclip.copy(contact_name)
                pyautogui.hotkey("command", "v")
                time.sleep(delay)
                pyautogui.press("enter")
                time.sleep(delay)
                message = f"Entered chat for contact search target: {contact_name}"
                LOGGER.info(message)
                return UiActionResult("search_contact", True, message, attempt=attempt)
            except Exception as exc:
                screenshot_path = screenshot_func(config) if screenshot_func else None
                last_result = UiActionResult(
                    "search_contact",
                    False,
                    f"Failed to search WeChat contact {contact_name} on attempt {attempt}: {exc}",
                    attempt=attempt,
                    screenshot_path=screenshot_path,
                    error=str(exc),
                )
                LOGGER.error(last_result.message)

        if attempt < retry_count:
            time.sleep(delay)

    return last_result


def search_contact(contact_name: str, config: dict[str, Any]) -> bool:
    return search_contact_result(contact_name, config).ok
