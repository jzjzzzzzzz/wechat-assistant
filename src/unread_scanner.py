"""Fallback unread chat-list scanner for dry-run auto-reply planning."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.auto_reply_policy import AutoReplyEvent, auto_reply_config, should_ignore_by_name
from src.ocr_reader import read_image_text
from src.wechat_screenshot_verifier import ScreenshotVerification, WeChatScreenshotVerifier
from src.wechat_window import activate_wechat_result, get_wechat_window_rect
from src.window_capture import WindowCaptureResult, capture_wechat_window
from src.window_locator import WeChatWindow, WindowLocatorResult, find_wechat_windows


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackgroundScanResult:
    ok: bool
    message: str
    window: WeChatWindow | None = None
    capture: WindowCaptureResult | None = None
    verification: ScreenshotVerification | None = None
    error: str | None = None


def _is_wechat_frontmost(app_name: str = "WeChat") -> bool:
    script = 'tell application "System Events" to get name of first process whose frontmost is true'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        frontmost = result.stdout.strip()
        ok = frontmost == app_name
        if not ok:
            LOGGER.warning("Unread scan skipped: frontmost app is %r, not %r.", frontmost, app_name)
        return ok
    except Exception as exc:
        LOGGER.warning("Unread scan skipped: could not verify frontmost app: %s", exc)
        return False


def _capture_chat_list_area(config: dict[str, Any]) -> str | None:
    try:
        import pyautogui  # type: ignore
    except Exception as exc:  # pragma: no cover - local dependency
        LOGGER.error("Unread scan screenshot unavailable; pyautogui import failed: %s", exc)
        return None

    screenshot_dir = Path(config.get("screenshot_dir", "screenshots"))
    if not screenshot_dir.is_absolute():
        screenshot_dir = Path(__file__).resolve().parents[1] / screenshot_dir
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    output_path = screenshot_dir / f"unread_chat_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    rect = get_wechat_window_rect()
    try:
        full_image = pyautogui.screenshot()
        display_width, display_height = pyautogui.size()
        scale_x = full_image.width / float(display_width or full_image.width)
        scale_y = full_image.height / float(display_height or full_image.height)
        if rect is None:
            region = (0, 0, min(360, int(display_width)), int(display_height))
        else:
            x, y, _width, height = rect
            region = (x, y, 360, height)
        left = max(0, int(region[0] * scale_x))
        top = max(0, int(region[1] * scale_y))
        right = min(full_image.width, int((region[0] + region[2]) * scale_x))
        bottom = min(full_image.height, int((region[1] + region[3]) * scale_y))
        image = full_image.crop((left, top, right, bottom))
        image.save(output_path)
        LOGGER.info("Captured unread chat list screenshot: %s", output_path)
        return str(output_path)
    except Exception as exc:  # pragma: no cover - permission dependent
        LOGGER.error(
            "Unread scan screenshot failed. Enable Screen Recording permission for the terminal. Error: %s",
            exc,
        )
        return None


def _looks_unread(text: str) -> bool:
    return "未读" in text


def _candidate_names(ocr_items: list[dict[str, Any]]) -> list[tuple[str, float, str]]:
    candidates: list[tuple[str, float]] = []
    previous_text = ""
    previous_confidence = 0.0
    for item in ocr_items:
        text = str(item.get("text", "")).strip()
        confidence = float(item.get("confidence", 0.0))
        if not text:
            continue
        if _looks_unread(text):
            name = previous_text if previous_text else text
            candidates.append((name, min(confidence, previous_confidence or confidence), text))
        previous_text = text
        previous_confidence = confidence
    return candidates


def _background_config(config: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "enabled": True,
        "prefer_background_capture": True,
        "allow_activate_wechat_fallback": False,
        "require_screenshot_verification": True,
        "verifier_min_confidence": 0.70,
        "debug_screenshot_dir": "screenshots/background_scan",
        "max_scan_interval_seconds": 30,
    }
    raw = config.get("background_scan", {})
    if isinstance(raw, dict):
        defaults.update(raw)
    return defaults


def _ocr_image(
    image_path: str,
    *,
    ocr_func: Callable[..., list[dict[str, Any]]] = read_image_text,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    try:
        return ocr_func(image_path, min_confidence=min_confidence)
    except TypeError:
        return ocr_func(image_path)


def run_background_scan_once(
    config: dict[str, Any],
    *,
    locator_func: Callable[..., WindowLocatorResult] = find_wechat_windows,
    capture_func: Callable[[WeChatWindow, dict[str, Any]], WindowCaptureResult] = capture_wechat_window,
    verifier_factory: Callable[..., WeChatScreenshotVerifier] = WeChatScreenshotVerifier,
    verifier_ocr_func: Callable[..., list[dict[str, Any]]] = read_image_text,
) -> BackgroundScanResult:
    bg = _background_config(config)
    if not bg.get("enabled", True):
        return BackgroundScanResult(False, "Background scan is disabled by config.")

    app_name = str(config.get("wechat_app_name", "WeChat"))
    try:
        located = locator_func(app_name=app_name)
    except TypeError:
        located = locator_func()
    except Exception as exc:
        LOGGER.warning("Background scan window lookup failed safely: %s", exc)
        return BackgroundScanResult(False, "WeChat window lookup failed.", error=str(exc))

    if not located.ok or not located.windows:
        message = located.message or "WeChat window not found."
        LOGGER.info("Background scan skipped: %s", message)
        return BackgroundScanResult(False, message, error=located.error)

    window = located.windows[0]
    if not window.can_attempt_background_capture:
        return BackgroundScanResult(False, "WeChat window not visible or capturable.", window=window)

    capture = capture_func(window, config)
    if not capture.ok or not capture.image_path:
        return BackgroundScanResult(
            False,
            capture.message,
            window=window,
            capture=capture,
            error=capture.error,
        )

    if bg.get("require_screenshot_verification", True):
        verifier = verifier_factory(min_confidence=float(bg.get("verifier_min_confidence", 0.70)))
        verification = verifier.verify_image(
            capture.image_path,
            ocr_func=lambda path: _ocr_image(
                str(path),
                ocr_func=verifier_ocr_func,
                min_confidence=max(0.0, float(config.get("ocr_confidence_threshold", 0.3))),
            ),
        )
        if not verification.ok:
            LOGGER.warning(
                "Background scan skipped OCR: screenshot verification failed confidence=%.3f reason=%s",
                verification.confidence,
                verification.reason,
            )
            return BackgroundScanResult(
                False,
                "WeChat screenshot verification failed.",
                window=window,
                capture=capture,
                verification=verification,
            )
        return BackgroundScanResult(True, "Background WeChat screenshot verified.", window, capture, verification)

    return BackgroundScanResult(True, "Background WeChat screenshot captured without verification.", window, capture)


def _events_from_ocr_items(
    config: dict[str, Any],
    ocr_items: list[dict[str, Any]],
    *,
    now_func: Callable[[], datetime] = datetime.now,
    source_confidence_multiplier: float = 1.0,
) -> list[AutoReplyEvent]:
    ar = auto_reply_config(config)
    now = now_func()
    events: list[AutoReplyEvent] = []
    for sender, confidence, unread_marker in _candidate_names(ocr_items):
        reason = should_ignore_by_name(sender, ar)
        if reason:
            LOGGER.info("Unread scan ignored %r: %s", sender, reason)
            continue
        confidence = min(1.0, confidence * source_confidence_multiplier)
        if confidence < float(ar.get("min_ocr_confidence", 0.65)):
            LOGGER.info("Unread scan ignored %r: confidence %.3f below minimum.", sender, confidence)
            continue
        events.append(
            AutoReplyEvent(
                source="unread_chat_scan",
                sender=sender,
                message_preview=unread_marker,
                detected_at=now,
                first_seen_at=now,
                last_seen_at=now,
                confidence=confidence,
                status="pending",
                is_private_candidate=True,
            )
        )
    return events


def _legacy_activate_scan_unread_events(
    config: dict[str, Any],
    *,
    activate_func: Callable[..., Any] = activate_wechat_result,
    frontmost_func: Callable[[str], bool] = _is_wechat_frontmost,
    capture_func: Callable[[dict[str, Any]], str | None] = _capture_chat_list_area,
    ocr_func: Callable[..., list[dict[str, Any]]] = read_image_text,
    now_func: Callable[[], datetime] = datetime.now,
) -> list[AutoReplyEvent]:
    app_name = str(config.get("wechat_app_name", "WeChat"))
    activation = activate_func(app_name, wait_seconds=0.5, retry_count=1)
    if hasattr(activation, "ok") and not activation.ok:
        LOGGER.warning("Unread scan skipped: %s", getattr(activation, "message", "activation failed"))
        return []
    if activation is False:
        LOGGER.warning("Unread scan skipped: WeChat activation failed.")
        return []
    if not frontmost_func(app_name):
        return []

    screenshot_path = capture_func(config)
    if not screenshot_path:
        LOGGER.warning("Unread scan skipped: screenshot unavailable.")
        return []

    try:
        ar = auto_reply_config(config)
        ocr_items = _ocr_image(
            screenshot_path,
            ocr_func=ocr_func,
            min_confidence=max(0.0, float(ar.get("min_ocr_confidence", 0.65)) - 0.2),
        )
    except Exception as exc:
        LOGGER.error("Unread scan OCR failed safely: %s", exc)
        return []
    events = _events_from_ocr_items(config, ocr_items, now_func=now_func)
    LOGGER.info("Legacy unread scan produced %s auto-reply candidate(s).", len(events))
    return events


def scan_unread_events(
    config: dict[str, Any],
    *,
    locator_func: Callable[..., WindowLocatorResult] = find_wechat_windows,
    window_capture_func: Callable[[WeChatWindow, dict[str, Any]], WindowCaptureResult] = capture_wechat_window,
    verifier_factory: Callable[..., WeChatScreenshotVerifier] = WeChatScreenshotVerifier,
    activate_func: Callable[..., Any] = activate_wechat_result,
    frontmost_func: Callable[[str], bool] = _is_wechat_frontmost,
    capture_func: Callable[[dict[str, Any]], str | None] = _capture_chat_list_area,
    ocr_func: Callable[..., list[dict[str, Any]]] = read_image_text,
    now_func: Callable[[], datetime] = datetime.now,
) -> list[AutoReplyEvent]:
    bg = _background_config(config)
    events: list[AutoReplyEvent] = []
    if bg.get("enabled", True) and bg.get("prefer_background_capture", True):
        result = run_background_scan_once(
            config,
            locator_func=locator_func,
            capture_func=window_capture_func,
            verifier_factory=verifier_factory,
            verifier_ocr_func=ocr_func,
        )
        if result.ok and result.capture and result.capture.image_path:
            try:
                ar = auto_reply_config(config)
                ocr_items = _ocr_image(
                    result.capture.image_path,
                    ocr_func=ocr_func,
                    min_confidence=max(0.0, float(ar.get("min_ocr_confidence", 0.65)) - 0.2),
                )
            except Exception as exc:
                LOGGER.error("Background unread OCR failed safely: %s", exc)
                return []
            verification_confidence = result.verification.confidence if result.verification else 0.8
            events = _events_from_ocr_items(
                config,
                ocr_items,
                now_func=now_func,
                source_confidence_multiplier=max(0.5, verification_confidence),
            )
            LOGGER.info("Background unread scan produced %s auto-reply candidate(s).", len(events))
            return events

        LOGGER.info("Background unread scan produced no candidates: %s", result.message)

    if bg.get("allow_activate_wechat_fallback", False):
        return _legacy_activate_scan_unread_events(
            config,
            activate_func=activate_func,
            frontmost_func=frontmost_func,
            capture_func=capture_func,
            ocr_func=ocr_func,
            now_func=now_func,
        )

    LOGGER.info("Activation fallback disabled; unread scan complete with no candidates.")
    return events


def unread_scan_once(config: dict[str, Any]) -> list[AutoReplyEvent]:
    return scan_unread_events(config)
