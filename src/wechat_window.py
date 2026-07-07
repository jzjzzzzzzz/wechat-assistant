"""WeChat for Mac window control helpers."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Any, cast


LOGGER = logging.getLogger(__name__)

# Sidebar width (logical pixels) — left contact-list panel in WeChat for Mac.
_WECHAT_SIDEBAR_WIDTH = 240
# Distance from window bottom to the centre of the chat input box (logical px).
_INPUT_BOX_OFFSET_FROM_BOTTOM = 35


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


def get_wechat_window_rect() -> tuple[int, int, int, int] | None:
    """Return (x, y, width, height) of the WeChat main window in logical pixels.

    Returns None when the window cannot be found or AppleScript fails.
    """
    script = """
tell application "System Events"
    tell process "WeChat"
        set wins to windows
        repeat with w in wins
            if name of w is "Weixin" then
                set {wx, wy} to position of w
                set {ww, wh} to size of w
                return (wx as string) & "," & (wy as string) & "," & (ww as string) & "," & (wh as string)
            end if
        end repeat
    end tell
end tell
"""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        raw = result.stdout.strip()
        if not raw:
            LOGGER.warning("get_wechat_window_rect: AppleScript returned empty string")
            return None
        parts = [int(v) for v in raw.split(",")]
        if len(parts) != 4:
            LOGGER.warning("get_wechat_window_rect: unexpected output %r", raw)
            return None
        LOGGER.info("WeChat window rect (logical): x=%s y=%s w=%s h=%s", *parts)
        return cast(tuple[int, int, int, int], tuple(parts))
    except Exception as exc:
        LOGGER.error("get_wechat_window_rect failed: %s", exc)
        return None


def click_chat_input_box(app_name: str = "WeChat", interval: float = 0.2) -> bool:
    """Click the chat input box so keyboard focus lands there.

    Calculates the input-box coordinates from the live WeChat window geometry
    so the click is accurate even when the window has been moved or resized.
    Falls back gracefully when pyautogui or window geometry is unavailable.
    """
    pyautogui, import_error = _import_pyautogui()
    if import_error:
        LOGGER.error("click_chat_input_box: pyautogui unavailable: %s", import_error)
        return False

    rect = get_wechat_window_rect()
    if rect is None:
        LOGGER.warning("click_chat_input_box: could not determine window rect; skipping click")
        return False

    wx, wy, ww, wh = rect
    input_x = wx + _WECHAT_SIDEBAR_WIDTH + (ww - _WECHAT_SIDEBAR_WIDTH) // 2
    input_y = wy + wh - _INPUT_BOX_OFFSET_FROM_BOTTOM
    LOGGER.info("Clicking chat input box at logical (%s, %s)", input_x, input_y)
    try:
        pyautogui.click(input_x, input_y)
        time.sleep(interval)
        return True
    except Exception as exc:
        LOGGER.error("click_chat_input_box failed: %s", exc)
        return False


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


def is_app_frontmost_result(app_name: str = "WeChat") -> UiActionResult:
    """Return whether *app_name* is the current frontmost macOS process."""
    script = f'tell application "System Events" to get frontmost of process "{app_name}"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        frontmost = result.returncode == 0 and result.stdout.strip().lower() == "true"
        message = f"Frontmost check for {app_name}: {frontmost}"
        if frontmost:
            LOGGER.info(message)
            return UiActionResult("is_app_frontmost", True, message)
        stderr = result.stderr.strip()
        message = f"{app_name} is not frontmost"
        if stderr:
            message = f"{message}: {stderr}"
        LOGGER.warning(message)
        return UiActionResult("is_app_frontmost", False, message, error=stderr or None)
    except Exception as exc:
        message = f"Failed to check frontmost app {app_name}: {exc}"
        LOGGER.error(message)
        return UiActionResult("is_app_frontmost", False, message, error=str(exc))


def set_app_frontmost_result(app_name: str = "WeChat") -> UiActionResult:
    """Best-effort Accessibility handoff to make *app_name* frontmost."""
    script = f'''
tell application "{app_name}" to activate
tell application "System Events"
    tell process "{app_name}"
        set frontmost to true
    end tell
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            message = f"Requested frontmost focus for {app_name}."
            LOGGER.info(message)
            return UiActionResult("set_app_frontmost", True, message)
        stderr = result.stderr.strip()
        message = f"Failed to set {app_name} frontmost: {stderr or 'osascript failed'}"
        LOGGER.warning(message)
        return UiActionResult("set_app_frontmost", False, message, error=stderr)
    except Exception as exc:
        message = f"Failed to set {app_name} frontmost: {exc}"
        LOGGER.error(message)
        return UiActionResult("set_app_frontmost", False, message, error=str(exc))


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
                    set_frontmost = set_app_frontmost_result(app_name)
                    time.sleep(wait_seconds)
                    frontmost = is_app_frontmost_result(app_name)
                    if frontmost.ok:
                        message = f"Activated WeChat window on attempt {attempt}; frontmost confirmed."
                        LOGGER.info(message)
                        return UiActionResult("activate_wechat", True, message, attempt=attempt)
                    last_result = UiActionResult(
                        "activate_wechat",
                        False,
                        (
                            f"Activated {app_name}, but frontmost verification failed: "
                            f"{frontmost.message}"
                        ),
                        attempt=attempt,
                        error=frontmost.error or set_frontmost.error,
                    )
                    LOGGER.error(last_result.message)
                stderr = result.stderr.strip()
                if result.returncode != 0:
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
    frontmost_func: Any | None = None,
) -> UiActionResult:
    app_name = config.get("wechat_app_name", "WeChat")
    delay = float(config.get("search_delay_seconds", 1.5))
    retry_count = int(config.get("max_retry", 3))
    interval = float(config.get("ui_action_interval_seconds", 0.2))
    frontmost_checker = frontmost_func or is_app_frontmost_result

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
                frontmost = frontmost_checker(app_name)
                if hasattr(frontmost, "ok"):
                    if not frontmost.ok:
                        raise RuntimeError(
                            f"WeChat is not frontmost before search shortcuts: {frontmost.message}"
                        )
                elif not frontmost:
                    raise RuntimeError("WeChat is not frontmost before search shortcuts")
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
                # After pressing Enter the contact chat opens, but keyboard focus
                # may still be on the search bar rather than the chat input box.
                # Explicitly click the input box so the next paste lands there.
                click_chat_input_box(app_name, interval=interval)
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
