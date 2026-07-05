"""Fallback unread chat-list scanner for dry-run auto-reply planning."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.auto_reply_policy import AutoReplyEvent, auto_reply_config, should_ignore_by_name
from src.ocr_reader import read_image_text
from src.wechat_window import activate_wechat_result, get_wechat_window_rect


LOGGER = logging.getLogger(__name__)


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
        if rect is None:
            width, height = pyautogui.size()
            region = (0, 0, min(360, int(width)), int(height))
        else:
            x, y, _width, height = rect
            region = (x, y, 360, height)
        image = pyautogui.screenshot(region=region)
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
    lowered = text.casefold()
    return any(marker in lowered for marker in ("未读", "unread", "[", "条"))


def _candidate_names(ocr_items: list[dict[str, Any]]) -> list[tuple[str, float]]:
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
            candidates.append((name, min(confidence, previous_confidence or confidence)))
        previous_text = text
        previous_confidence = confidence
    return candidates


def scan_unread_events(
    config: dict[str, Any],
    *,
    activate_func: Callable[..., Any] = activate_wechat_result,
    capture_func: Callable[[dict[str, Any]], str | None] = _capture_chat_list_area,
    ocr_func: Callable[..., list[dict[str, Any]]] = read_image_text,
    now_func: Callable[[], datetime] = datetime.now,
) -> list[AutoReplyEvent]:
    ar = auto_reply_config(config)
    app_name = str(config.get("wechat_app_name", "WeChat"))
    activation = activate_func(app_name, wait_seconds=0.5, retry_count=1)
    if hasattr(activation, "ok") and not activation.ok:
        LOGGER.warning("Unread scan skipped: %s", getattr(activation, "message", "activation failed"))
        return []
    if activation is False:
        LOGGER.warning("Unread scan skipped: WeChat activation failed.")
        return []

    screenshot_path = capture_func(config)
    if not screenshot_path:
        LOGGER.warning("Unread scan skipped: screenshot unavailable.")
        return []

    try:
        ocr_items = ocr_func(
            screenshot_path,
            min_confidence=max(0.0, float(ar.get("min_ocr_confidence", 0.65)) - 0.2),
        )
    except TypeError:
        ocr_items = ocr_func(screenshot_path)
    except Exception as exc:
        LOGGER.error("Unread scan OCR failed safely: %s", exc)
        return []

    now = now_func()
    events: list[AutoReplyEvent] = []
    for sender, confidence in _candidate_names(ocr_items):
        reason = should_ignore_by_name(sender, ar)
        if reason:
            LOGGER.info("Unread scan ignored %r: %s", sender, reason)
            continue
        if confidence < float(ar.get("min_ocr_confidence", 0.65)):
            LOGGER.info("Unread scan ignored %r: confidence %.3f below minimum.", sender, confidence)
            continue
        events.append(
            AutoReplyEvent(
                source="unread_chat_scan",
                sender=sender,
                message_preview="",
                detected_at=now,
                first_seen_at=now,
                last_seen_at=now,
                confidence=confidence,
                status="pending",
                is_private_candidate=True,
            )
        )
    LOGGER.info("Unread scan produced %s auto-reply candidate(s).", len(events))
    return events


def unread_scan_once(config: dict[str, Any]) -> list[AutoReplyEvent]:
    return scan_unread_events(config)
