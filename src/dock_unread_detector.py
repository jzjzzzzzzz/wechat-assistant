"""Safe Dock unread-badge detector.

This module inspects only the bottom Dock strip of the current screen.  It does
not OCR app content, does not activate WeChat, and does not touch the WeChat UI.

The detector is intentionally conservative:
- it first looks for a WeChat-like green Dock icon candidate;
- it then accepts only red badge candidates geometrically attached to that icon;
- if the Dock is hidden, on another display, or unclear, the result is unknown.

The result is used as an additional safety/trigger signal.  It must never be the
only evidence for a target sender; the normal WeChat notification/window
pipeline still has to identify the chat and pass the send gate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DockVisualCandidate:
    x: int
    y: int
    width: int
    height: int
    area: int
    confidence: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2


@dataclass(frozen=True)
class DockUnreadDetection:
    ok: bool
    has_unread: bool | None
    message: str
    confidence: float
    detected_at: datetime
    screenshot_path: str | None = None
    green_mask_path: str | None = None
    red_mask_path: str | None = None
    overlay_path: str | None = None
    wechat_icon_candidates: tuple[DockVisualCandidate, ...] = ()
    red_badge_candidates: tuple[DockVisualCandidate, ...] = ()
    associated_badges: tuple[str, ...] = ()
    rejected_reasons: tuple[str, ...] = ()
    error: str | None = None

    @property
    def safe_gate_value(self) -> bool | None:
        """Return the value that should be passed to should_auto_reply()."""
        return self.has_unread if self.ok else None


def dock_unread_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return Dock unread detection config.

    Missing config defaults to disabled so unit tests and older config dicts do
    not unexpectedly require a real macOS screenshot.  settings.yaml enables the
    detector for the real application.
    """
    defaults: dict[str, Any] = {
        "enabled": False,
        "require_for_auto_reply": False,
        "capture_bottom_pixels": 220,
        "debug_screenshot_dir": "screenshots/dock_scan",
        "min_confidence": 0.55,
        "min_red_badge_side": 6,
        "max_red_badge_side": 64,
        "min_green_icon_side": 24,
        "max_green_icon_side": 140,
    }
    raw = config.get("dock_unread", {})
    if isinstance(raw, dict):
        defaults.update(raw)
    defaults["enabled"] = bool(defaults.get("enabled", False))
    defaults["require_for_auto_reply"] = bool(defaults.get("require_for_auto_reply", False))
    defaults["capture_bottom_pixels"] = max(80, int(defaults.get("capture_bottom_pixels", 220)))
    defaults["min_confidence"] = max(0.0, min(1.0, float(defaults.get("min_confidence", 0.55))))
    defaults["min_red_badge_side"] = max(3, int(defaults.get("min_red_badge_side", 6)))
    defaults["max_red_badge_side"] = max(
        defaults["min_red_badge_side"] + 1,
        int(defaults.get("max_red_badge_side", 64)),
    )
    defaults["min_green_icon_side"] = max(10, int(defaults.get("min_green_icon_side", 24)))
    defaults["max_green_icon_side"] = max(
        defaults["min_green_icon_side"] + 1,
        int(defaults.get("max_green_icon_side", 140)),
    )
    return defaults


def _project_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved


def _debug_path(base_dir: str | Path, suffix: str) -> Path:
    output_dir = _project_path(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"dock_unread_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{suffix}.png"


def capture_dock_screenshot(config: dict[str, Any]) -> str | None:
    """Capture the bottom Dock strip and save it for debugging.

    Returns None on permission errors or if pyautogui is unavailable.
    """
    dock = dock_unread_config(config)
    output_path = _debug_path(dock["debug_screenshot_dir"], "screen")
    try:
        import pyautogui  # type: ignore

        screen_w, screen_h = pyautogui.size()
        height = min(int(dock["capture_bottom_pixels"]), int(screen_h))
        y = max(0, int(screen_h) - height)
        image = pyautogui.screenshot(region=(0, y, int(screen_w), height))
        image.save(output_path)
        LOGGER.info("Dock unread detector captured bottom strip: %s region=%s", output_path, (0, y, int(screen_w), height))
        return str(output_path)
    except Exception as exc:  # pragma: no cover - depends on macOS permissions
        LOGGER.warning(
            "Dock unread detector screenshot failed safely. Screen Recording permission may be needed: %s",
            exc,
        )
        return None


def _component_candidates(mask: Any, *, kind: str, config: dict[str, Any]) -> tuple[list[DockVisualCandidate], list[str]]:
    import cv2  # type: ignore

    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    dock = dock_unread_config(config)
    candidates: list[DockVisualCandidate] = []
    rejected: list[str] = []
    if kind == "green":
        min_side = int(dock["min_green_icon_side"])
        max_side = int(dock["max_green_icon_side"])
        min_area = max(120, min_side * min_side // 3)
    else:
        min_side = int(dock["min_red_badge_side"])
        max_side = int(dock["max_red_badge_side"])
        min_area = max(20, min_side * min_side // 2)

    for label in range(1, count):
        x, y, width, height, area = [int(value) for value in stats[label]]
        reason: str | None = None
        if width < min_side or height < min_side:
            reason = "too_small"
        elif width > max_side or height > max_side:
            reason = "too_large"
        elif area < min_area:
            reason = "area_too_small"
        aspect = width / float(height or 1)
        if reason is None and not 0.45 <= aspect <= 2.20:
            reason = "bad_aspect_ratio"
        fill_ratio = area / float(max(1, width * height))
        if reason is None and fill_ratio < (0.20 if kind == "red" else 0.25):
            reason = "fill_ratio_too_low"
        if reason is None:
            confidence = min(0.95, 0.45 + fill_ratio * 0.5)
            candidates.append(DockVisualCandidate(x, y, width, height, area, confidence))
        else:
            rejected.append(f"{kind}:x={x} y={y} w={width} h={height} area={area} reason={reason}")
    return candidates, rejected


def _is_badge_attached_to_wechat_icon(badge: DockVisualCandidate, icon: DockVisualCandidate) -> bool:
    badge_cx, badge_cy = badge.center
    icon_cx, icon_cy = icon.center
    x_min = icon.x - int(icon.width * 0.20)
    x_max = icon.x + icon.width + int(icon.width * 0.35)
    y_min = icon.y - int(icon.height * 0.40)
    y_max = icon.y + int(icon.height * 0.70)
    near_top_right = badge_cx >= icon_cx - int(icon.width * 0.15) and badge_cy <= icon_cy + int(icon.height * 0.15)
    return x_min <= badge_cx <= x_max and y_min <= badge_cy <= y_max and near_top_right


def analyze_dock_screenshot(image_path: str | Path, config: dict[str, Any]) -> DockUnreadDetection:
    """Analyze a saved Dock screenshot and return a structured result."""
    now = datetime.now()
    dock = dock_unread_config(config)
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency issue
        return DockUnreadDetection(
            False,
            None,
            "OpenCV unavailable for Dock unread detection.",
            0.0,
            now,
            screenshot_path=str(image_path),
            error=str(exc),
        )

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        return DockUnreadDetection(
            False,
            None,
            "Dock screenshot could not be loaded.",
            0.0,
            now,
            screenshot_path=str(image_path),
            error=f"could not load {image_path}",
        )

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, np.array([38, 45, 45]), np.array([95, 255, 255]))
    red_low = cv2.inRange(hsv, np.array([0, 70, 70]), np.array([12, 255, 255]))
    red_high = cv2.inRange(hsv, np.array([168, 70, 70]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(red_low, red_high)
    kernel = np.ones((3, 3), np.uint8)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    base_dir = dock["debug_screenshot_dir"]
    green_mask_path = _debug_path(base_dir, "green_mask")
    red_mask_path = _debug_path(base_dir, "red_mask")
    overlay_path = _debug_path(base_dir, "overlay")
    rejected: list[str] = []
    try:
        cv2.imwrite(str(green_mask_path), green_mask)
        cv2.imwrite(str(red_mask_path), red_mask)
    except Exception as exc:
        LOGGER.warning("Dock unread detector could not write mask debug images: %s", exc)

    green_candidates, green_rejected = _component_candidates(green_mask, kind="green", config=config)
    red_candidates, red_rejected = _component_candidates(red_mask, kind="red", config=config)
    rejected.extend(green_rejected)
    rejected.extend(red_rejected)

    associations: list[tuple[DockVisualCandidate, DockVisualCandidate]] = []
    for badge in red_candidates:
        for icon in green_candidates:
            if _is_badge_attached_to_wechat_icon(badge, icon):
                associations.append((icon, badge))
                break

    try:
        overlay = image.copy()
        for icon in green_candidates:
            cv2.rectangle(overlay, (icon.x, icon.y), (icon.x + icon.width, icon.y + icon.height), (0, 255, 0), 2)
        for badge in red_candidates:
            cv2.rectangle(overlay, (badge.x, badge.y), (badge.x + badge.width, badge.y + badge.height), (0, 0, 255), 2)
        for icon, badge in associations:
            cv2.line(overlay, icon.center, badge.center, (255, 0, 0), 2)
        cv2.imwrite(str(overlay_path), overlay)
    except Exception as exc:
        LOGGER.warning("Dock unread detector overlay write failed safely: %s", exc)

    if not green_candidates:
        return DockUnreadDetection(
            False,
            None,
            "WeChat Dock icon was not confidently found.",
            0.0,
            now,
            screenshot_path=str(image_path),
            green_mask_path=str(green_mask_path),
            red_mask_path=str(red_mask_path),
            overlay_path=str(overlay_path),
            red_badge_candidates=tuple(red_candidates),
            rejected_reasons=tuple(rejected),
        )

    if not associations:
        confidence = max((candidate.confidence for candidate in green_candidates), default=0.0)
        return DockUnreadDetection(
            True,
            False,
            "WeChat Dock icon found; no attached red unread badge detected.",
            confidence,
            now,
            screenshot_path=str(image_path),
            green_mask_path=str(green_mask_path),
            red_mask_path=str(red_mask_path),
            overlay_path=str(overlay_path),
            wechat_icon_candidates=tuple(green_candidates),
            red_badge_candidates=tuple(red_candidates),
            rejected_reasons=tuple(rejected),
        )

    icon, badge = max(associations, key=lambda pair: pair[0].confidence + pair[1].confidence)
    confidence = min(0.98, (icon.confidence + badge.confidence) / 2.0 + 0.12)
    ok = confidence >= float(dock["min_confidence"])
    message = "WeChat Dock red unread badge detected." if ok else "Dock unread evidence below confidence threshold."
    return DockUnreadDetection(
        ok,
        True if ok else None,
        message,
        confidence,
        now,
        screenshot_path=str(image_path),
        green_mask_path=str(green_mask_path),
        red_mask_path=str(red_mask_path),
        overlay_path=str(overlay_path),
        wechat_icon_candidates=tuple(green_candidates),
        red_badge_candidates=tuple(red_candidates),
        associated_badges=(
            f"icon=({icon.x},{icon.y},{icon.width},{icon.height}) "
            f"badge=({badge.x},{badge.y},{badge.width},{badge.height})",
        ),
        rejected_reasons=tuple(rejected),
    )


def detect_dock_wechat_unread(
    config: dict[str, Any],
    *,
    capture_func: Callable[[dict[str, Any]], str | None] = capture_dock_screenshot,
    now_func: Callable[[], datetime] = datetime.now,
) -> DockUnreadDetection:
    """Capture and analyze the Dock unread badge state.

    Never raises.  Disabled or unclear detection returns has_unread=None.
    """
    dock = dock_unread_config(config)
    now = now_func()
    if not dock.get("enabled", False):
        return DockUnreadDetection(False, None, "Dock unread detector disabled by config.", 0.0, now)
    try:
        path = capture_func(config)
    except Exception as exc:
        LOGGER.warning("Dock unread capture callable failed safely: %s", exc)
        return DockUnreadDetection(False, None, "Dock unread screenshot failed.", 0.0, now, error=str(exc))
    if not path:
        return DockUnreadDetection(False, None, "Dock unread screenshot unavailable.", 0.0, now)
    try:
        detection = analyze_dock_screenshot(path, config)
    except Exception as exc:
        LOGGER.warning("Dock unread analysis failed safely: %s", exc)
        return DockUnreadDetection(False, None, "Dock unread analysis failed.", 0.0, now, screenshot_path=path, error=str(exc))
    LOGGER.info(
        "Dock unread detection: ok=%s has_unread=%s confidence=%.3f message=%s screenshot=%s",
        detection.ok,
        detection.has_unread,
        detection.confidence,
        detection.message,
        detection.screenshot_path,
    )
    return detection
