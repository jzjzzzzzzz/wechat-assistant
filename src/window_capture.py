"""Window and visible-region capture skeleton for background WeChat scanning."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.window_locator import WeChatWindow


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WindowCaptureResult:
    ok: bool
    image_path: str | None
    method: str
    message: str
    error: str | None = None


def _debug_dir(config: dict[str, Any]) -> Path:
    background = config.get("background_scan", {})
    configured = "screenshots/background_scan"
    if isinstance(background, dict):
        configured = str(background.get("debug_screenshot_dir", configured))
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _output_path(config: dict[str, Any], *, prefix: str) -> Path:
    return _debug_dir(config) / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"


def capture_window_by_id(window: WeChatWindow, config: dict[str, Any]) -> WindowCaptureResult:
    """Try macOS window-id capture.

    This is intentionally conservative. If Quartz screen-capture symbols are
    unavailable on the local Python/macOS combination, callers should fallback
    to visible-region capture.
    """
    if window.window_id is None:
        return WindowCaptureResult(False, None, "window_id", "Window id is unavailable.")

    output_path = _output_path(config, prefix=f"wechat_window_{window.window_id}")
    try:
        import Quartz  # type: ignore
        from PIL import Image  # type: ignore

        image_ref = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            int(window.window_id),
            Quartz.kCGWindowImageBoundsIgnoreFraming,
        )
        if image_ref is None:
            return WindowCaptureResult(False, None, "window_id", "Window-id capture returned no image.")

        width = Quartz.CGImageGetWidth(image_ref)
        height = Quartz.CGImageGetHeight(image_ref)
        provider = Quartz.CGImageGetDataProvider(image_ref)
        data = Quartz.CGDataProviderCopyData(provider)
        image = Image.frombuffer("RGBA", (width, height), bytes(data), "raw", "BGRA", 0, 1)
        image.save(output_path)
        return WindowCaptureResult(True, str(output_path), "window_id", "Captured WeChat window by id.")
    except Exception as exc:  # pragma: no cover - macOS permission/API dependent
        LOGGER.warning("Window-id capture failed safely: %s", exc)
        return WindowCaptureResult(
            False,
            None,
            "window_id",
            "Window-id capture failed. Screen Recording permission may be required.",
            error=str(exc),
        )


def capture_visible_region(
    window: WeChatWindow,
    config: dict[str, Any],
    *,
    screenshot_func: Callable[[], Any] | None = None,
    size_func: Callable[[], tuple[int, int]] | None = None,
) -> WindowCaptureResult:
    if not window.can_attempt_background_capture:
        return WindowCaptureResult(False, None, "visible_region", "Window is hidden, minimized, or implausible.")

    output_path = _output_path(config, prefix="wechat_visible_region")
    try:
        if screenshot_func is None or size_func is None:
            import pyautogui  # type: ignore

            screenshot_func = screenshot_func or pyautogui.screenshot
            size_func = size_func or pyautogui.size

        full_image = screenshot_func()
        display_width, display_height = size_func()
        scale_x = full_image.width / float(display_width or full_image.width)
        scale_y = full_image.height / float(display_height or full_image.height)
        bounds = window.bounds
        left = max(0, int(bounds.x * scale_x))
        top = max(0, int(bounds.y * scale_y))
        right = min(full_image.width, int((bounds.x + bounds.width) * scale_x))
        bottom = min(full_image.height, int((bounds.y + bounds.height) * scale_y))
        if right <= left or bottom <= top:
            return WindowCaptureResult(False, None, "visible_region", "Window bounds are outside the display.")
        full_image.crop((left, top, right, bottom)).save(output_path)
        return WindowCaptureResult(True, str(output_path), "visible_region", "Captured visible WeChat region.")
    except Exception as exc:  # pragma: no cover - permission/local display dependent
        LOGGER.warning("Visible-region capture failed safely: %s", exc)
        return WindowCaptureResult(
            False,
            None,
            "visible_region",
            "Visible-region capture failed. Screen Recording permission may be required.",
            error=str(exc),
        )


def capture_wechat_window(window: WeChatWindow, config: dict[str, Any]) -> WindowCaptureResult:
    if not window.can_attempt_background_capture:
        return WindowCaptureResult(False, None, "none", "Window is hidden, minimized, or not visible.")

    by_id = capture_window_by_id(window, config)
    if by_id.ok:
        return by_id
    return capture_visible_region(window, config)
