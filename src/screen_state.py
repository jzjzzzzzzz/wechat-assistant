"""Conservative visible-screen state detection for WeChat automation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)


class ScreenState(str, Enum):
    UNKNOWN = "unknown"
    WECHAT_ACTIVE = "wechat_active"
    SEARCH_OPEN = "search_open"
    CHAT_OPEN = "chat_open"
    INPUT_READY = "input_ready"


@dataclass(frozen=True)
class ScreenStateDetection:
    state: ScreenState
    confidence: float
    source: str | None
    message: str

    @property
    def ok_for_real_send(self) -> bool:
        return self.state in {ScreenState.CHAT_OPEN, ScreenState.INPUT_READY}


def unknown_state(message: str, source: str | None = None) -> ScreenStateDetection:
    LOGGER.info("Screen state unknown. source=%s message=%s", source, message)
    return ScreenStateDetection(
        state=ScreenState.UNKNOWN,
        confidence=0.0,
        source=source,
        message=message,
    )


def infer_state_from_text(text_items: list[str], source: str | None = None) -> ScreenStateDetection:
    normalized = " ".join(item.strip() for item in text_items if item.strip())
    if not normalized:
        return unknown_state("No OCR text available for screen-state inference.", source)

    if "搜索" in normalized or "Search" in normalized:
        return ScreenStateDetection(
            ScreenState.SEARCH_OPEN,
            0.45,
            source,
            "Search-like text found in visible OCR output.",
        )
    if "发送" in normalized or "Send" in normalized:
        return ScreenStateDetection(
            ScreenState.INPUT_READY,
            0.5,
            source,
            "Send-like text found in visible OCR output.",
        )

    return unknown_state("Visible OCR text did not match a known WeChat state.", source)


def detect_screen_state(image_path: str | Path | None, ocr_items: list[str] | None = None) -> ScreenStateDetection:
    if image_path is None:
        return unknown_state("No screenshot path provided.")

    path = Path(image_path)
    if not path.exists():
        return unknown_state(f"Screenshot path does not exist: {path}", str(path))

    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
        LOGGER.info("Loaded screenshot for screen-state detection: %s size=%sx%s", path, width, height)
    except Exception as exc:
        return unknown_state(f"Could not load screenshot for screen-state detection: {exc}", str(path))

    if ocr_items:
        return infer_state_from_text(ocr_items, str(path))

    return unknown_state(
        "Screenshot loaded, but no reliable visual detector is available yet.",
        str(path),
    )


def real_send_allowed_by_screen_state(detection: ScreenStateDetection) -> tuple[bool, str]:
    if detection.ok_for_real_send:
        return True, f"Screen state allows real send: {detection.state.value}"
    return False, f"Screen state blocks real send: {detection.state.value} ({detection.message})"
