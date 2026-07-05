"""macOS WeChat notification OCR detection for dry-run auto-reply planning."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.auto_reply_policy import AutoReplyEvent, auto_reply_config, should_ignore_by_name
from src.ocr_reader import read_image_text


LOGGER = logging.getLogger(__name__)


def _capture_notification_area(config: dict[str, Any]) -> str | None:
    screenshot_dir = Path(config.get("screenshot_dir", "screenshots"))
    if not screenshot_dir.is_absolute():
        screenshot_dir = Path(__file__).resolve().parents[1] / screenshot_dir
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    output_path = screenshot_dir / f"notification_area_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    try:
        import pyautogui  # type: ignore

        width, height = pyautogui.size()
        region_width = min(520, int(width))
        region_height = min(360, int(height))
        image = pyautogui.screenshot(region=(int(width) - region_width, 0, region_width, region_height))
        image.save(output_path)
        LOGGER.info("Captured notification area screenshot: %s", output_path)
        return str(output_path)
    except Exception as exc:  # pragma: no cover - local macOS permission dependent
        LOGGER.error(
            "Notification screenshot failed. Enable Screen Recording permission for the terminal. Error: %s",
            exc,
        )
        return None


def _text_confidence(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    return max(float(item.get("confidence", 0.0)) for item in items)


def _extract_sender_preview(texts: list[str]) -> tuple[str, str]:
    cleaned = [text.strip() for text in texts if text.strip()]
    if not cleaned:
        return "unknown", ""

    wechat_indexes = [i for i, text in enumerate(cleaned) if "微信" in text or "WeChat" in text]
    if wechat_indexes:
        idx = wechat_indexes[0]
        remaining = cleaned[idx + 1 :]
    else:
        remaining = cleaned

    sender = remaining[0] if remaining else "unknown"
    preview = " ".join(remaining[1:]).strip()

    if ":" in sender and not preview:
        before, after = sender.split(":", 1)
        sender = before.strip() or "unknown"
        preview = after.strip()
    if "：" in sender and not preview:
        before, after = sender.split("：", 1)
        sender = before.strip() or "unknown"
        preview = after.strip()
    return sender or "unknown", preview


def detect_notification_events(
    config: dict[str, Any],
    *,
    capture_func: Callable[[dict[str, Any]], str | None] = _capture_notification_area,
    ocr_func: Callable[..., list[dict[str, Any]]] = read_image_text,
    now_func: Callable[[], datetime] = datetime.now,
) -> list[AutoReplyEvent]:
    ar = auto_reply_config(config)
    screenshot_path = capture_func(config)
    if not screenshot_path:
        LOGGER.warning("Notification detection skipped: screenshot unavailable.")
        return []

    try:
        ocr_items = ocr_func(
            screenshot_path,
            min_confidence=max(0.0, float(ar.get("min_ocr_confidence", 0.65)) - 0.2),
        )
    except TypeError:
        ocr_items = ocr_func(screenshot_path)
    except Exception as exc:
        LOGGER.error("Notification OCR failed safely: %s", exc)
        return []

    texts = [str(item.get("text", "")).strip() for item in ocr_items if str(item.get("text", "")).strip()]
    combined = " ".join(texts)
    if "微信" not in combined and "WeChat" not in combined:
        LOGGER.info("Notification OCR ignored: no WeChat marker found.")
        return []

    confidence = _text_confidence(ocr_items)
    if confidence < float(ar.get("min_ocr_confidence", 0.65)):
        LOGGER.info("Notification OCR ignored: confidence %.3f below minimum.", confidence)
        return []

    sender, preview = _extract_sender_preview(texts)
    reason = should_ignore_by_name(sender, ar)
    if reason:
        LOGGER.info("Notification OCR ignored: %s", reason)
        return []

    now = now_func()
    event = AutoReplyEvent(
        source="notification_ocr",
        sender=sender,
        message_preview=preview,
        detected_at=now,
        first_seen_at=now,
        last_seen_at=now,
        confidence=confidence,
        status="pending",
        is_private_candidate=True,
    )
    LOGGER.info("Notification auto-reply candidate detected: sender=%s confidence=%.3f", sender, confidence)
    return [event]


def notification_check_once(config: dict[str, Any]) -> list[AutoReplyEvent]:
    return detect_notification_events(config)
