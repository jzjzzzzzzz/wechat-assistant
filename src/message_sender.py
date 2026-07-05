"""Safe WeChat test message sending."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from src.screenshot import capture_screenshot
from src.screen_state import ScreenStateDetection, detect_screen_state, real_send_allowed_by_screen_state
from src.wechat_window import UiActionResult, search_contact


LOGGER = logging.getLogger(__name__)
SAFE_TEST_CONTACT = "文件传输助手"


def is_real_send_enabled(config: dict[str, Any], target: str) -> tuple[bool, str]:
    if config.get("dry_run", True):
        return False, "dry_run is true"
    if not config.get("allow_real_send", False):
        return False, "allow_real_send is false"
    if target != SAFE_TEST_CONTACT:
        return False, f"real sending is restricted to {SAFE_TEST_CONTACT}"
    return True, "real send enabled"


def _paste_message(message: str) -> bool:
    try:
        import pyautogui  # type: ignore
        import pyperclip  # type: ignore

        pyperclip.copy(message)
        pyautogui.hotkey("command", "v")
        return True
    except Exception as exc:
        LOGGER.error("Failed to paste message: %s", exc)
        return False


def _press_enter() -> bool:
    try:
        import pyautogui  # type: ignore

        pyautogui.press("enter")
        return True
    except Exception as exc:
        LOGGER.error("Failed to press Enter: %s", exc)
        return False


def _real_send_screen_state_check(
    config: dict[str, Any],
    screenshot_func: Callable[[dict[str, Any]], str | None],
    screen_state_func: Callable[[str | None], ScreenStateDetection],
) -> tuple[bool, str]:
    if not config.get("require_known_screen_state_for_real_send", True):
        return True, "screen-state real-send check disabled by config"

    screenshot_path = screenshot_func(config)
    detection = screen_state_func(screenshot_path)
    allowed, reason = real_send_allowed_by_screen_state(detection)
    if allowed:
        LOGGER.info(reason)
    else:
        LOGGER.warning(reason)
    return allowed, reason


def send_message(
    config: dict[str, Any],
    target: str,
    message: str,
    *,
    search_func: Callable[[str, dict[str, Any]], bool | UiActionResult] = search_contact,
    paste_func: Callable[[str], bool] = _paste_message,
    enter_func: Callable[[], bool] = _press_enter,
    screenshot_func: Callable[[dict[str, Any]], str | None] = capture_screenshot,
    screen_state_func: Callable[[str | None], ScreenStateDetection] = detect_screen_state,
) -> bool:
    LOGGER.info("Preparing message. Target=%s dry_run=%s", target, config.get("dry_run", True))

    can_send, reason = is_real_send_enabled(config, target)
    if config.get("dry_run", True):
        print(f"DRY RUN: would send to {target}: {message}")
        LOGGER.info("Dry run only. No WeChat UI action performed. Reason: %s", reason)
        return True

    if not can_send:
        print(f"REAL SEND BLOCKED: {reason}")
        LOGGER.warning("Real send blocked for target=%s. Reason: %s", target, reason)
        return False

    screen_ok, screen_reason = _real_send_screen_state_check(config, screenshot_func, screen_state_func)
    if not screen_ok:
        print(f"REAL SEND BLOCKED: {screen_reason}")
        LOGGER.warning("Real send blocked before UI action. Reason: %s", screen_reason)
        return False

    print("REAL SEND ENABLED")
    print(f"Target: {target}")
    print(f"Message: {message}")
    LOGGER.warning("REAL SEND ENABLED. Target=%s Message=%s", target, message)

    max_retry = int(config.get("max_retry", 3))
    for attempt in range(1, max_retry + 1):
        LOGGER.info("Send attempt %s/%s for target=%s", attempt, max_retry, target)
        try:
            search_result = search_func(target, config)
            if isinstance(search_result, UiActionResult):
                if not search_result.ok:
                    raise RuntimeError(search_result.message)
            elif not search_result:
                raise RuntimeError("contact search failed")
            if not paste_func(message):
                raise RuntimeError("message paste failed")
            time.sleep(float(config.get("send_delay_seconds", 1.0)))
            if not enter_func():
                raise RuntimeError("press Enter failed")
            screenshot_path = screenshot_func(config)
            LOGGER.info("Message sent. Screenshot after send: %s", screenshot_path)
            return True
        except Exception as exc:
            screenshot_path = screenshot_func(config)
            LOGGER.error("Send attempt %s failed: %s. Screenshot: %s", attempt, exc, screenshot_path)
            if attempt < max_retry:
                time.sleep(float(config.get("send_delay_seconds", 1.0)))

    LOGGER.error("All send attempts failed for target=%s", target)
    return False


def send_test_message(config: dict[str, Any]) -> bool:
    target = str(config.get("test_contact", SAFE_TEST_CONTACT))
    message = str(config.get("test_message", "WeChat Assistant test message"))
    return send_message(config, target, message)
