"""Fallback unread chat-list scanner for dry-run auto-reply planning."""

from __future__ import annotations

import logging
import re
import subprocess
import time
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
NON_PRIVATE_SENDER_KEYWORDS = (
    "Official Accounts",
    "Service Accounts",
    "Weixin Games",
    "WeChat Pay",
    "WeChat Team",
    "Subscriptions",
    "Subscription",
    "公众号",
    "订阅号",
    "服务通知",
    "微信支付",
    "微信团队",
)


@dataclass(frozen=True)
class BackgroundScanResult:
    ok: bool
    message: str
    window: WeChatWindow | None = None
    capture: WindowCaptureResult | None = None
    verification: ScreenshotVerification | None = None
    error: str | None = None


@dataclass(frozen=True)
class UnreadBadge:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    count: int | None = None

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass(frozen=True)
class ChatListRow:
    index: int
    x: int
    y: int
    width: int
    height: int

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    def contains_point(self, x: int, y: int) -> bool:
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


@dataclass(frozen=True)
class BadgeRowAssociation:
    row: ChatListRow
    badge: UnreadBadge
    sender: str
    confidence: float
    marker: str
    evidence: str


@dataclass(frozen=True)
class IgnoredBadgeCandidate:
    badge: UnreadBadge
    row: ChatListRow | None
    reason: str
    evidence: str


@dataclass(frozen=True)
class RejectedRedContour:
    x: int
    y: int
    width: int
    height: int
    area: int
    reason: str


@dataclass(frozen=True)
class BadgeDetectionDiagnostics:
    badges: list[UnreadBadge]
    rejected_contours: list[RejectedRedContour]
    contour_count: int
    chat_list_crop_path: str | None = None
    red_mask_path: str | None = None
    contour_overlay_path: str | None = None


@dataclass(frozen=True)
class UnreadScanReport:
    screenshot_path: str | None
    chat_list_crop_path: str | None
    red_mask_path: str | None
    contour_overlay_path: str | None
    row_overlay_path: str | None
    contour_count: int
    accepted_badge_count: int
    rejected_contour_count: int
    row_count: int
    association_count: int
    final_candidate_count: int
    ignored_reasons: list[str]
    badge_candidates: list[str]


_LAST_UNREAD_SCAN_REPORT: UnreadScanReport | None = None


def get_last_unread_scan_report() -> UnreadScanReport | None:
    return _LAST_UNREAD_SCAN_REPORT


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
    candidates: list[tuple[str, float, str]] = []
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


def _bbox_center(bbox: Any) -> tuple[float, float] | None:
    if not bbox:
        return None
    try:
        points = [(float(point[0]), float(point[1])) for point in bbox]
    except Exception:
        return None
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _bbox_bounds(bbox: Any) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    try:
        xs = [float(point[0]) for point in bbox]
        ys = [float(point[1]) for point in bbox]
    except Exception:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _is_possible_chat_name(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped.isdigit() or _looks_unread(stripped):
        return False
    if re.fullmatch(r"(Today|Yesterday|\d{1,2}:\d{2}|[A-Za-z]+day\s+\d{1,2}:\d{2}).*", stripped):
        return False
    ui_labels = {
        "微信",
        "WeChat",
        "Weixin",
        "Search",
        "Contacts",
        "Chats",
        "Friend Profile",
        "Remark",
        "Moments",
        "More Info",
        "Message",
        "Messages",
        "Voice Call",
        "Video Call",
    }
    return stripped not in ui_labels


def _non_private_sender_reason(sender: str) -> str | None:
    for keyword in NON_PRIVATE_SENDER_KEYWORDS:
        if keyword and keyword in sender:
            return f"non_private_sender_keyword:{keyword}"
    return None


def _debug_image_path(image_path: str | Path, suffix: str) -> Path:
    path = Path(image_path)
    return path.with_name(f"{path.stem}_{suffix}.png")


def _chat_list_bounds(width: int, height: int) -> tuple[int, int, int, int]:
    left = max(70, int(width * 0.04))
    right = min(int(width * 0.36), int(width * 0.43))
    top = int(height * 0.04)
    bottom = height
    return left, top, max(left + 1, right), bottom


def _component_circularity(component_mask: Any) -> float:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        contours, _hierarchy = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0.0
        contour = max(contours, key=cv2.contourArea)
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            return 0.0
        area = float(cv2.countNonZero(component_mask))
        return float((4.0 * np.pi * area) / (perimeter * perimeter))
    except Exception:
        return 0.0


def detect_unread_badges_with_diagnostics(image_path: str | Path) -> BadgeDetectionDiagnostics:
    """Detect red unread dots/numeric badges and return debug evidence."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        LOGGER.warning("Unread badge detection skipped; OpenCV unavailable: %s", exc)
        return BadgeDetectionDiagnostics([], [], 0)

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        LOGGER.warning("Unread badge detection skipped; could not load image: %s", image_path)
        return BadgeDetectionDiagnostics([], [], 0)

    height, width = image.shape[:2]
    if width < 300 or height < 300:
        return BadgeDetectionDiagnostics([], [], 0)

    chat_left, chat_top, chat_right, chat_bottom = _chat_list_bounds(width, height)
    chat_crop_path = _debug_image_path(image_path, "chat_list_crop")
    try:
        cv2.imwrite(str(chat_crop_path), image[chat_top:chat_bottom, chat_left:chat_right])
    except Exception as exc:
        LOGGER.warning("Could not write chat-list crop debug image: %s", exc)
        chat_crop_path = None  # type: ignore[assignment]

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red_low = cv2.inRange(hsv, np.array([0, 70, 80]), np.array([12, 255, 255]))
    red_high = cv2.inRange(hsv, np.array([168, 70, 80]), np.array([180, 255, 255]))
    mask = cv2.bitwise_or(red_low, red_high)

    # Ignore the left app sidebar and the main content pane. The real unread
    # numeric badge observed at x~=199 in a 1760px-wide screenshot must pass,
    # while the sidebar badge at x~=67 must be rejected.
    badge_x_min = chat_left
    badge_x_max = chat_right
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    red_mask_path = _debug_image_path(image_path, "red_mask")
    try:
        cv2.imwrite(str(red_mask_path), mask)
    except Exception as exc:
        LOGGER.warning("Could not write red mask debug image: %s", exc)
        red_mask_path = None  # type: ignore[assignment]

    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    badges: list[UnreadBadge] = []
    rejected: list[RejectedRedContour] = []
    min_side = max(5, int(min(width, height) * 0.006))
    max_side = max(18, int(min(width, height) * 0.055))
    for label in range(1, count):
        x, y, component_width, component_height, area = [int(value) for value in stats[label]]
        component_mask = mask[y : y + component_height, x : x + component_width]
        circularity = _component_circularity(component_mask)
        reason: str | None = None
        if component_width < min_side or component_height < min_side:
            reason = "too_small"
        elif component_width > max_side or component_height > max_side:
            reason = "too_large"
        elif area < max(18, min_side * min_side // 2):
            reason = "area_too_small"
        aspect = component_width / float(component_height or 1)
        if reason is None and not 0.45 <= aspect <= 2.20:
            reason = "bad_aspect_ratio"
        fill_ratio = area / float(component_width * component_height)
        if reason is None and (component_width < 20 or component_height < 20) and area < 400:
            reason = "likely_text_fragment"
        if reason is None and fill_ratio < 0.22:
            reason = "fill_ratio_too_low"
        if reason is None and circularity < 0.32:
            reason = "low_circularity"
        cx = x + component_width // 2
        cy = y + component_height // 2
        if reason is None and cy < int(height * 0.05):
            reason = "top_window_chrome_region"
        if reason is None and x < badge_x_min:
            reason = "left_sidebar_or_avatar_region"
        if reason is None and cx > badge_x_max:
            reason = "outside_chat_list"
        if reason is None:
            confidence = min(1.0, 0.55 + fill_ratio * 0.35)
            badges.append(
                UnreadBadge(
                    x,
                    y,
                    component_width,
                    component_height,
                    confidence,
                    count=_infer_numeric_badge_count(image, x, y, component_width, component_height),
                )
            )
        else:
            rejected.append(RejectedRedContour(x, y, component_width, component_height, area, reason))

    badges.sort(key=lambda badge: (badge.y, badge.x))
    contour_overlay_path = _debug_image_path(image_path, "contour_overlay")
    try:
        overlay = image.copy()
        for badge in badges:
            cv2.rectangle(
                overlay,
                (badge.x, badge.y),
                (badge.x + badge.width, badge.y + badge.height),
                (0, 255, 0),
                3,
            )
        for item in rejected:
            cv2.rectangle(
                overlay,
                (item.x, item.y),
                (item.x + item.width, item.y + item.height),
                (0, 0, 255),
                2,
            )
        cv2.rectangle(overlay, (chat_left, chat_top), (chat_right, chat_bottom), (255, 0, 0), 2)
        cv2.imwrite(str(contour_overlay_path), overlay)
    except Exception as exc:
        LOGGER.warning("Could not write contour overlay debug image: %s", exc)
        contour_overlay_path = None  # type: ignore[assignment]

    LOGGER.info("Detected %s red unread badge candidate(s).", len(badges))
    for badge in badges:
        LOGGER.info(
            "Accepted red badge x=%s y=%s w=%s h=%s confidence=%.3f count=%s",
            badge.x,
            badge.y,
            badge.width,
            badge.height,
            badge.confidence,
            badge.count,
        )
    for item in rejected:
        LOGGER.info(
            "Rejected red contour x=%s y=%s w=%s h=%s area=%s reason=%s",
            item.x,
            item.y,
            item.width,
            item.height,
            item.area,
            item.reason,
        )
    return BadgeDetectionDiagnostics(
        badges=badges,
        rejected_contours=rejected,
        contour_count=max(0, count - 1),
        chat_list_crop_path=str(chat_crop_path) if chat_crop_path else None,
        red_mask_path=str(red_mask_path) if red_mask_path else None,
        contour_overlay_path=str(contour_overlay_path) if contour_overlay_path else None,
    )


def detect_unread_badges(image_path: str | Path) -> list[UnreadBadge]:
    """Detect red unread dots/numeric badges in the WeChat chat-list area."""
    return detect_unread_badges_with_diagnostics(image_path).badges


def _infer_numeric_badge_count(image: Any, x: int, y: int, width: int, height: int) -> int | None:
    """Infer a single-digit numeric badge when OCR misses white text.

    This intentionally only returns 1. Other counts should come from OCR near
    the badge. Empty red dots usually have no white pixels in the badge crop.
    """
    if width < 18 or height < 18:
        return None
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        crop = image[y : y + height, x : x + width]
        if crop.size == 0:
            return None
        white_mask = cv2.inRange(crop, np.array([210, 210, 210]), np.array([255, 255, 255]))
        white_pixels = int(cv2.countNonZero(white_mask))
        if white_pixels < max(8, int(width * height * 0.018)):
            return None
        count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(white_mask, connectivity=8)
        for label in range(1, count):
            _cx, _cy, component_width, component_height, area = [int(value) for value in stats[label]]
            if area >= 6 and component_height >= height * 0.25 and component_width <= width * 0.45:
                return 1
    except Exception:
        return None
    return None


def segment_chat_list_rows(image_path: str | Path) -> list[ChatListRow]:
    """Return conservative row slots for the visible WeChat chat/contact list.

    This is geometry-first: it does not require OCR text boxes to decide which
    row a red badge belongs to. The fixed-row estimate matches WeChat's visible
    list structure well enough for row-level evidence, while OCR remains only
    for naming the row.
    """
    try:
        from PIL import Image  # type: ignore

        with Image.open(image_path) as image:
            width, height = image.size
    except Exception as exc:
        LOGGER.warning("Chat-list row segmentation skipped; image unavailable: %s", exc)
        return []

    if width < 300 or height < 300:
        return []

    x = int(width * 0.01)
    panel_right = int(width * 0.43)
    row_width = max(1, panel_right - x)
    y_start = int(height * 0.08)
    # WeChat's visible chat rows are about 128-132 px tall on the 1760x1280
    # Retina screenshots we capture from Window Services.  The previous 0.085
    # ratio made rows too short, so a preview from the row above could be
    # associated with the unread badge below it.
    row_height = max(54, min(136, int(height * 0.102)))
    rows: list[ChatListRow] = []
    index = 0
    y = y_start
    while y + row_height <= height - int(height * 0.02):
        rows.append(ChatListRow(index=index, x=x, y=y, width=row_width, height=row_height))
        index += 1
        y += row_height
    LOGGER.info("Segmented %s chat-list row slot(s).", len(rows))
    return rows


def _associate_badges_with_ocr_rows(
    badges: list[UnreadBadge],
    ocr_items: list[dict[str, Any]],
    *,
    image_height: int | None = None,
) -> list[tuple[str, float, str]]:
    rows: list[tuple[str, float, float, float]] = []
    for item in ocr_items:
        text = str(item.get("text", "")).strip()
        if not _is_possible_chat_name(text):
            continue
        center = _bbox_center(item.get("bbox"))
        bounds = _bbox_bounds(item.get("bbox"))
        if center is None or bounds is None:
            continue
        x1, _y1, x2, _y2 = bounds
        confidence = float(item.get("confidence", 0.0))
        # Chat names are normally left of the red badge, not in the detail pane.
        rows.append((text, confidence, center[0], center[1]))

    if not rows:
        return []

    max_y_distance = 48.0
    if image_height:
        max_y_distance = max(36.0, min(90.0, image_height * 0.045))

    associated: list[tuple[str, float, str]] = []
    used_names: set[str] = set()
    for badge in badges:
        badge_x, badge_y = badge.center
        nearest: tuple[str, float, float, float] | None = None
        nearest_distance = float("inf")
        for row in rows:
            name, row_confidence, row_x, row_y = row
            if name in used_names:
                continue
            if row_x >= badge_x:
                continue
            distance = abs(row_y - badge_y)
            if distance < nearest_distance:
                nearest = row
                nearest_distance = distance
        if nearest is None or nearest_distance > max_y_distance:
            continue
        name, row_confidence, _row_x, _row_y = nearest
        used_names.add(name)
        confidence = min(row_confidence, badge.confidence)
        count = badge.count if badge.count is not None else _badge_count_from_ocr(badge, ocr_items)
        marker = f"red_unread_badge:{count}" if count is not None else "red_unread_badge"
        associated.append((name, confidence, marker))
    return associated


def _text_items_in_row(row: ChatListRow, ocr_items: list[dict[str, Any]]) -> list[tuple[str, float, float]]:
    items: list[tuple[str, float, float]] = []
    for item in ocr_items:
        text = str(item.get("text", "")).strip()
        if not _is_possible_chat_name(text):
            continue
        center = _bbox_center(item.get("bbox"))
        if center is None:
            continue
        cx, cy = center
        if row.contains_point(int(cx), int(cy)):
            items.append((text, float(item.get("confidence", 0.0)), cx))
    items.sort(key=lambda value: value[2])
    return items


def _sender_items_in_row(row: ChatListRow, ocr_items: list[dict[str, Any]]) -> list[tuple[str, float, float, float]]:
    items: list[tuple[str, float, float, float]] = []
    sender_left = row.x + int(row.width * 0.12)
    sender_right = row.x + int(row.width * 0.62)
    sender_bottom = row.y + int(row.height * 0.66)
    for item in ocr_items:
        text = str(item.get("text", "")).strip()
        if not _is_possible_chat_name(text):
            continue
        bounds = _bbox_bounds(item.get("bbox"))
        center = _bbox_center(item.get("bbox"))
        if bounds is None or center is None:
            continue
        x1, y1, x2, y2 = bounds
        cx, cy = center
        if cx < sender_left or cx > sender_right:
            continue
        if x1 > sender_right or y1 > sender_bottom or cy > sender_bottom:
            continue
        if not row.contains_point(int(cx), int(cy)):
            continue
        confidence = float(item.get("confidence", 0.0))
        top_line_bonus = max(0.0, 1.0 - max(0.0, (cy - row.y) / float(row.height or 1)))
        left_bonus = max(0.0, 1.0 - max(0.0, (cx - row.x) / float(row.width or 1)))
        text_bonus = min(0.2, len(text) * 0.01)
        score = confidence + 0.15 * top_line_bonus + 0.1 * left_bonus + text_bonus
        items.append((text, confidence, score, cx))
    items.sort(key=lambda value: (-value[2], value[3]))
    return items


def associate_badges_with_rows_diagnostics(
    badges: list[UnreadBadge],
    rows: list[ChatListRow],
    ocr_items: list[dict[str, Any]],
) -> tuple[list[BadgeRowAssociation], list[IgnoredBadgeCandidate]]:
    associations: list[BadgeRowAssociation] = []
    ignored: list[IgnoredBadgeCandidate] = []
    used_rows: set[int] = set()
    for badge in badges:
        badge_x, badge_y = badge.center
        containing_rows = [row for row in rows if row.contains_point(badge_x, badge_y)]
        if containing_rows:
            row = min(containing_rows, key=lambda candidate: abs(candidate.center_y - badge_y))
        elif rows:
            row = min(rows, key=lambda candidate: abs(candidate.center_y - badge_y))
            if abs(row.center_y - badge_y) > row.height * 0.65:
                ignored.append(
                    IgnoredBadgeCandidate(
                        badge=badge,
                        row=row,
                        reason="not_row_aligned",
                        evidence=(
                            f"nearest_row={row.index} row_bounds=({row.x},{row.y},{row.width},{row.height}) "
                            f"badge_bounds=({badge.x},{badge.y},{badge.width},{badge.height})"
                        ),
                    )
                )
                continue
        else:
            ignored.append(
                IgnoredBadgeCandidate(
                    badge=badge,
                    row=None,
                    reason="no_chat_rows_segmented",
                    evidence=f"badge_bounds=({badge.x},{badge.y},{badge.width},{badge.height})",
                )
            )
            continue

        if row.index in used_rows:
            ignored.append(
                IgnoredBadgeCandidate(
                    badge=badge,
                    row=row,
                    reason="row_already_used",
                    evidence=f"row={row.index} badge_bounds=({badge.x},{badge.y},{badge.width},{badge.height})",
                )
            )
            continue
        row_sender_items = _sender_items_in_row(row, ocr_items)
        if not row_sender_items:
            ignored.append(
                IgnoredBadgeCandidate(
                    badge=badge,
                    row=row,
                    reason="sender_ocr_failed",
                    evidence=(
                        f"row={row.index} row_bounds=({row.x},{row.y},{row.width},{row.height}) "
                        f"badge_bounds=({badge.x},{badge.y},{badge.width},{badge.height})"
                    ),
                )
            )
            continue

        sender, sender_confidence, _sender_score, _sender_x = row_sender_items[0]
        count = badge.count if badge.count is not None else _badge_count_from_ocr(badge, ocr_items)
        marker = f"red_unread_badge:{count}" if count is not None else "red_unread_badge"
        confidence = min(sender_confidence, badge.confidence)
        used_rows.add(row.index)
        associations.append(
            BadgeRowAssociation(
                row=row,
                badge=badge,
                sender=sender,
                confidence=confidence,
                marker=marker,
                evidence=(
                    f"row={row.index} row_bounds=({row.x},{row.y},{row.width},{row.height}) "
                    f"badge_bounds=({badge.x},{badge.y},{badge.width},{badge.height})"
                ),
            )
        )
    LOGGER.info("Associated %s unread badge(s) with chat-list row evidence.", len(associations))
    for item in ignored:
        LOGGER.info("Ignored badge candidate reason=%s %s", item.reason, item.evidence)
    return associations, ignored


def associate_badges_with_rows(
    badges: list[UnreadBadge],
    rows: list[ChatListRow],
    ocr_items: list[dict[str, Any]],
) -> list[BadgeRowAssociation]:
    associations, _ignored = associate_badges_with_rows_diagnostics(badges, rows, ocr_items)
    return associations


def _badge_count_from_ocr(badge: UnreadBadge, ocr_items: list[dict[str, Any]]) -> int | None:
    badge_x1 = badge.x - badge.width * 0.4
    badge_y1 = badge.y - badge.height * 0.4
    badge_x2 = badge.x + badge.width * 1.4
    badge_y2 = badge.y + badge.height * 1.4
    for item in ocr_items:
        text = str(item.get("text", "")).strip()
        if not text.isdigit():
            continue
        center = _bbox_center(item.get("bbox"))
        if center is None:
            continue
        cx, cy = center
        if badge_x1 <= cx <= badge_x2 and badge_y1 <= cy <= badge_y2:
            value = int(text)
            if 1 <= value <= 99:
                return value
    return None


def _image_height(image_path: str | Path) -> int | None:
    try:
        from PIL import Image  # type: ignore

        with Image.open(image_path) as image:
            return int(image.height)
    except Exception:
        return None


def write_badge_debug_overlay(
    image_path: str | Path,
    rows: list[ChatListRow],
    badges: list[UnreadBadge],
    associations: list[BadgeRowAssociation],
) -> str | None:
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as exc:  # pragma: no cover - pillow runtime dependency
        LOGGER.warning("Badge debug overlay skipped; Pillow unavailable: %s", exc)
        return None

    path = Path(image_path)
    output_path = path.with_name(f"{path.stem}_badge_overlay.png")
    try:
        with Image.open(path).convert("RGB") as image:
            draw = ImageDraw.Draw(image)
            for row in rows:
                draw.rectangle(
                    (row.x, row.y, row.x + row.width, row.y + row.height),
                    outline=(50, 150, 255),
                    width=2,
                )
                draw.text((row.x + 4, row.y + 4), f"row {row.index}", fill=(50, 150, 255))
            for badge in badges:
                draw.rectangle(
                    (badge.x, badge.y, badge.x + badge.width, badge.y + badge.height),
                    outline=(255, 0, 0),
                    width=3,
                )
            for association in associations:
                badge_x, badge_y = association.badge.center
                draw.line(
                    (association.row.x, association.row.center_y, badge_x, badge_y),
                    fill=(0, 180, 80),
                    width=3,
                )
                draw.text(
                    (association.row.x + 8, association.row.y + association.row.height - 18),
                    association.sender,
                    fill=(0, 140, 70),
                )
            image.save(output_path)
        LOGGER.info("Unread badge debug overlay saved: %s", output_path)
        return str(output_path)
    except Exception as exc:
        LOGGER.warning("Badge debug overlay failed safely: %s", exc)
        return None


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


def _unread_scan_config(config: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "enable_scroll_scan": False,
        "max_scroll_pages": 5,
        "scroll_amount": -5,
        "scroll_pause_seconds": 0.5,
        "restore_position_after_scan": True,
        "stop_on_first_private_candidate": True,
        "ignore_public_accounts": True,
        "ignore_service_accounts": True,
        "ignore_group_chats": True,
    }
    raw = config.get("unread_scan", {})
    if isinstance(raw, dict):
        defaults.update(raw)
    defaults["enable_scroll_scan"] = bool(defaults.get("enable_scroll_scan", False))
    defaults["max_scroll_pages"] = max(0, int(defaults.get("max_scroll_pages", 5)))
    defaults["scroll_amount"] = int(defaults.get("scroll_amount", -5))
    defaults["scroll_pause_seconds"] = max(0.0, float(defaults.get("scroll_pause_seconds", 0.5)))
    defaults["restore_position_after_scan"] = bool(defaults.get("restore_position_after_scan", True))
    defaults["stop_on_first_private_candidate"] = bool(defaults.get("stop_on_first_private_candidate", True))
    return defaults


def _chat_list_scroll_point(window: WeChatWindow) -> tuple[int, int] | None:
    if not window.can_attempt_background_capture:
        return None
    bounds = window.bounds
    if bounds.width < 300 or bounds.height < 300:
        return None
    x_offset = min(max(140, int(bounds.width * 0.12)), int(bounds.width * 0.35))
    y_offset = int(bounds.height * 0.45)
    return bounds.x + x_offset, bounds.y + y_offset


def _scroll_at_point(scroll_func: Callable[..., Any], amount: int, point: tuple[int, int]) -> None:
    x, y = point
    try:
        scroll_func(amount, x=x, y=y)
    except TypeError:
        scroll_func(amount)


def _default_scroll_func() -> Callable[..., Any] | None:
    try:
        import pyautogui  # type: ignore

        return pyautogui.scroll
    except Exception as exc:  # pragma: no cover - local GUI dependency
        LOGGER.warning("Scroll scan unavailable; pyautogui import failed: %s", exc)
        return None


def _without_scroll_scan(config: dict[str, Any]) -> dict[str, Any]:
    copied = dict(config)
    unread = dict(copied.get("unread_scan", {}))
    unread["enable_scroll_scan"] = False
    copied["unread_scan"] = unread
    return copied


def _merge_unique_events(base: list[AutoReplyEvent], extra: list[AutoReplyEvent]) -> list[AutoReplyEvent]:
    seen = {(event.source, event.sender) for event in base}
    merged = list(base)
    for event in extra:
        key = (event.source, event.sender)
        if key in seen:
            continue
        seen.add(key)
        merged.append(event)
    return merged


def _run_optional_scroll_scan(
    config: dict[str, Any],
    *,
    window: WeChatWindow | None,
    page_scan_func: Callable[[], list[AutoReplyEvent]],
    scroll_func: Callable[..., Any] | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
) -> list[AutoReplyEvent]:
    scan_config = _unread_scan_config(config)
    if not scan_config.get("enable_scroll_scan", False):
        return []
    if window is None:
        LOGGER.warning("Scroll scan skipped: chat-list region cannot be determined without a verified WeChat window.")
        return []
    point = _chat_list_scroll_point(window)
    if point is None:
        LOGGER.warning("Scroll scan skipped: chat-list region cannot be safely determined.")
        return []
    scroll = scroll_func or _default_scroll_func()
    if scroll is None:
        LOGGER.warning("Scroll scan skipped: scroll function unavailable.")
        return []

    max_pages = int(scan_config["max_scroll_pages"])
    amount = int(scan_config["scroll_amount"])
    pause = float(scan_config["scroll_pause_seconds"])
    restore = bool(scan_config["restore_position_after_scan"])
    stop_on_first = bool(scan_config["stop_on_first_private_candidate"])
    if max_pages <= 0 or amount == 0:
        LOGGER.info("Scroll scan skipped: max pages or scroll amount is zero.")
        return []

    events: list[AutoReplyEvent] = []
    pages_scrolled = 0
    try:
        for page in range(max_pages):
            _scroll_at_point(scroll, amount, point)
            pages_scrolled += 1
            LOGGER.info("Scroll scan page=%s amount=%s point=%s", page + 1, amount, point)
            if pause:
                sleep_func(pause)
            page_events = page_scan_func()
            events = _merge_unique_events(events, page_events)
            if page_events and stop_on_first:
                break
    except Exception as exc:
        LOGGER.warning("Scroll scan failed safely: %s", exc)
    finally:
        if restore and pages_scrolled:
            try:
                _scroll_at_point(scroll, -amount * pages_scrolled, point)
                LOGGER.info("Scroll scan restore attempted; certainty=uncertain pages=%s", pages_scrolled)
            except Exception as exc:
                LOGGER.warning("Scroll scan restore failed safely; certainty=uncertain error=%s", exc)
    return events


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
    badge_candidates: list[tuple[str, float, str, str | None]] | None = None,
    ignored_reasons_out: list[str] | None = None,
) -> list[AutoReplyEvent]:
    ar = auto_reply_config(config)
    now = now_func()
    events: list[AutoReplyEvent] = []
    candidate_rows = [
        *[(sender, confidence, marker, None) for sender, confidence, marker in _candidate_names(ocr_items)],
        *(badge_candidates or []),
    ]
    seen: set[str] = set()
    for sender, confidence, unread_marker, evidence in candidate_rows:
        if sender in seen:
            continue
        seen.add(sender)
        reason = should_ignore_by_name(sender, ar)
        reason = reason or _non_private_sender_reason(sender)
        if reason:
            LOGGER.info("Unread scan ignored %r: %s", sender, reason)
            if ignored_reasons_out is not None:
                if "blocklist keyword" in reason:
                    ignored_reasons_out.append(f"ignored_sender:{sender}:blocklisted_sender")
                elif "non-private keyword" in reason or reason.startswith("non_private_sender_keyword:"):
                    ignored_reasons_out.append(f"ignored_sender:{sender}:non_private_sender")
                elif "private chat whitelist" in reason:
                    ignored_reasons_out.append(f"ignored_sender:{sender}:not_in_private_whitelist")
                elif "group chat" in reason:
                    ignored_reasons_out.append(f"ignored_sender:{sender}:group_chat_candidate")
                elif reason == "unknown sender":
                    ignored_reasons_out.append(f"ignored_sender:{sender}:unknown_sender")
                ignored_reasons_out.append(f"ignored_sender:{sender}:{reason}")
            continue
        confidence = min(1.0, confidence * source_confidence_multiplier)
        if confidence < float(ar.get("min_ocr_confidence", 0.65)):
            LOGGER.info("Unread scan ignored %r: confidence %.3f below minimum.", sender, confidence)
            if ignored_reasons_out is not None:
                ignored_reasons_out.append(f"ignored_sender:{sender}:low_confidence")
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
        if evidence:
            LOGGER.info("Unread candidate row evidence sender=%s %s", sender, evidence)
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
    badge_detector_func: Callable[[str | Path], list[UnreadBadge]] = detect_unread_badges,
    now_func: Callable[[], datetime] = datetime.now,
    scroll_func: Callable[..., Any] | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
) -> list[AutoReplyEvent]:
    global _LAST_UNREAD_SCAN_REPORT
    _LAST_UNREAD_SCAN_REPORT = None
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
            try:
                if badge_detector_func is detect_unread_badges:
                    badge_diagnostics = detect_unread_badges_with_diagnostics(result.capture.image_path)
                    badges = badge_diagnostics.badges
                else:
                    badges = badge_detector_func(result.capture.image_path)
                    badge_diagnostics = BadgeDetectionDiagnostics(badges, [], len(badges))
            except Exception as exc:
                LOGGER.warning("Unread badge detection failed safely: %s", exc)
                badges = []
                badge_diagnostics = BadgeDetectionDiagnostics([], [], 0)
            rows = segment_chat_list_rows(result.capture.image_path)
            row_associations, ignored_badges = associate_badges_with_rows_diagnostics(badges, rows, ocr_items)
            overlay_path = write_badge_debug_overlay(
                result.capture.image_path,
                rows,
                badges,
                row_associations,
            )
            if overlay_path:
                LOGGER.info("Unread scan row-level debug overlay: %s", overlay_path)
            row_badge_candidates: list[tuple[str, float, str, str | None]] = [
                (association.sender, association.confidence, association.marker, association.evidence)
                for association in row_associations
            ]
            fallback_badge_candidates = _associate_badges_with_ocr_rows(
                badges,
                ocr_items,
                image_height=_image_height(result.capture.image_path),
            )
            fallback_badge_candidates_with_evidence = [
                (sender, confidence, marker, "fallback=ocr_bbox_nearest_row")
                for sender, confidence, marker in fallback_badge_candidates
                if sender not in {candidate[0] for candidate in row_badge_candidates}
            ]
            badge_candidates = [*row_badge_candidates, *fallback_badge_candidates_with_evidence]
            event_ignored_reasons: list[str] = []
            events = _events_from_ocr_items(
                config,
                ocr_items,
                now_func=now_func,
                source_confidence_multiplier=max(0.5, verification_confidence),
                badge_candidates=badge_candidates,
                ignored_reasons_out=event_ignored_reasons,
            )
            ignored_reasons = [
                *(f"rejected_contour:{item.reason}" for item in badge_diagnostics.rejected_contours),
                *(f"ignored_badge:{item.reason}" for item in ignored_badges),
                *event_ignored_reasons,
            ]
            _LAST_UNREAD_SCAN_REPORT = UnreadScanReport(
                screenshot_path=result.capture.image_path,
                chat_list_crop_path=badge_diagnostics.chat_list_crop_path,
                red_mask_path=badge_diagnostics.red_mask_path,
                contour_overlay_path=badge_diagnostics.contour_overlay_path,
                row_overlay_path=overlay_path,
                contour_count=badge_diagnostics.contour_count,
                accepted_badge_count=len(badges),
                rejected_contour_count=len(badge_diagnostics.rejected_contours),
                row_count=len(rows),
                association_count=len(row_associations),
                final_candidate_count=len(events),
                ignored_reasons=ignored_reasons,
                badge_candidates=[
                    (
                        f"x={badge.x} y={badge.y} w={badge.width} h={badge.height} "
                        f"confidence={badge.confidence:.3f} count={badge.count}"
                    )
                    for badge in badges
                ],
            )
            LOGGER.info("Background unread scan produced %s auto-reply candidate(s).", len(events))
            unread_config = _unread_scan_config(config)
            if (
                unread_config.get("enable_scroll_scan", False)
                and not (events and unread_config.get("stop_on_first_private_candidate", True))
            ):
                no_scroll_config = _without_scroll_scan(config)

                def page_scan() -> list[AutoReplyEvent]:
                    return scan_unread_events(
                        no_scroll_config,
                        locator_func=locator_func,
                        window_capture_func=window_capture_func,
                        verifier_factory=verifier_factory,
                        activate_func=activate_func,
                        frontmost_func=frontmost_func,
                        capture_func=capture_func,
                        ocr_func=ocr_func,
                        badge_detector_func=badge_detector_func,
                        now_func=now_func,
                        scroll_func=None,
                        sleep_func=sleep_func,
                    )

                scrolled_events = _run_optional_scroll_scan(
                    config,
                    window=result.window,
                    page_scan_func=page_scan,
                    scroll_func=scroll_func,
                    sleep_func=sleep_func,
                )
                events = _merge_unique_events(events, scrolled_events)
            return events

        LOGGER.info("Background unread scan produced no candidates: %s", result.message)
        if _unread_scan_config(config).get("enable_scroll_scan", False):
            _run_optional_scroll_scan(
                config,
                window=result.window,
                page_scan_func=lambda: [],
                scroll_func=scroll_func,
                sleep_func=sleep_func,
            )

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
