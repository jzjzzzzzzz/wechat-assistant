"""Realtime macOS OL/OFF status detection via visual/OCR evidence.

Reads the configured WeChat Assistant status-control region and maps the
visible label/color to an owner status value:

  Screen shows "OL" / "Online" / "WA ONLINE" → status = "active"   (owner online)
  Screen shows "OFF" / "Offline" / "WA OFFLINE" → status = "inactive" (owner offline)
  Unreadable / ambiguous → status = "unknown"  (safe default: no send)

The detector is used by the auto-reply daemon to keep the project
database in sync with whatever the user has set on the status menu
(rumps menu bar app).  Every state transition is logged.

Terminology note — "active" vs "online":
  The OwnerStatusStore stores "online" / "offline".
  The detector returns "active" / "inactive" / "unknown" to avoid confusion.
  The mapping: active → "online" stored,  inactive → "offline" stored.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.owner_status import OwnerStatusStore, validate_owner_status
from src.status_window import status_window_options


LOGGER = logging.getLogger(__name__)

# Fallback pixels from the top of the screen to capture when dedicated status
# window capture is disabled.
_MENU_BAR_HEIGHT = 220
# Fallback width of the menu-bar strip to inspect for status labels.
_CAPTURE_WIDTH = 560
_STATUS_BUTTON_PADDING_X = 8
_STATUS_BUTTON_PADDING_Y = 6

# Text tokens that indicate the system is ACTIVE (OL / Online).
_ONLINE_TOKENS: frozenset[str] = frozenset({
    "OL",
    "0L",
    "WA ONLINE",
    "WA OL",
    "ONLINE",
    "在线",
})

# Text tokens that indicate the system is INACTIVE (OFF / Offline).
_OFFLINE_TOKENS: frozenset[str] = frozenset({
    "OFF",
    "WA OFFLINE",
    "WA OFF",
    "OFFLINE",
    "离线",
})


@dataclass(frozen=True)
class MacosStatusDetection:
    """Result of one status-control scan."""

    raw_status: str          # "active", "inactive", or "unknown"
    db_status: str           # "online", "offline", or "unknown" (stored in DB)
    detected_text: str       # OCR text that triggered the decision
    screenshot_path: str | None
    detected_at: datetime
    confidence: float

    @property
    def is_active(self) -> bool:
        return self.raw_status == "active"

    @property
    def is_unknown(self) -> bool:
        return self.raw_status == "unknown"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _tokenize_status_text(text: str) -> list[str]:
    """Return coarse OCR tokens without matching OL inside unrelated words.

    OCR sometimes returns the menu item together with nearby clock text, e.g.
    "OL 10:32" or "WA ONLINE Tue".  We accept exact status tokens inside that
    text, but we do not treat substrings such as the "ol" in "Control" as OL.
    """
    stripped = re.sub(r"^[🟢🔴⚪🟡\s]+", "", _normalize(text)).strip()
    return re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", stripped)


def _classify_text(texts: list[str]) -> tuple[str, str]:
    """Return (raw_status, matched_text) from a list of OCR strings.

    Checks each text against known online/offline token sets.
    If both online and offline tokens are present, returns 'unknown'.
    Returns 'unknown' if nothing matches.
    """
    matches: list[tuple[str, str]] = []
    for raw in texts:
        cleaned = _normalize(raw)
        # Strip leading emoji (🟢 🔴 ⚪) and whitespace.
        stripped = re.sub(r"^[🟢🔴⚪🟡\s]+", "", cleaned).strip()
        tokens = [token.upper() for token in _tokenize_status_text(cleaned)]
        token_set = set(tokens)
        upper_stripped = stripped.upper()
        upper_cleaned = cleaned.upper()

        for token in _ONLINE_TOKENS:
            upper_token = token.upper()
            if (
                upper_stripped == upper_token
                or upper_cleaned == upper_token
                or upper_token in token_set
                or (upper_token in {"WA ONLINE", "WA OL"} and upper_token in upper_cleaned)
                or (token in {"在线"} and token in cleaned and "离线" not in cleaned)
            ):
                matches.append(("active", cleaned))
                break

        for token in _OFFLINE_TOKENS:
            upper_token = token.upper()
            if (
                upper_stripped == upper_token
                or upper_cleaned == upper_token
                or upper_token in token_set
                or (upper_token in {"WA OFFLINE", "WA OFF"} and upper_token in upper_cleaned)
                or (token in {"离线"} and token in cleaned)
            ):
                matches.append(("inactive", cleaned))
                break

    statuses = {status for status, _text in matches}
    if len(statuses) == 1:
        return matches[0]
    if len(statuses) > 1:
        LOGGER.warning("MacosStatusDetector: conflicting OL/OFF OCR tokens: %r", texts)

    return "unknown", ""


def _status_to_db_value(raw_status: str) -> str:
    """Map detector output to OwnerStatusStore values ('online' / 'offline')."""
    if raw_status == "active":
        return "online"
    if raw_status == "inactive":
        return "offline"
    return "unknown"


def _macos_status_config(config: dict[str, Any]) -> dict[str, Any]:
    status_config = config.get("macos_status", {})
    if not isinstance(status_config, dict):
        status_config = {}
    return status_config


def _capture_region(screen_width: int, config: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return the screen region used for status detection.

    Default mode captures only the expected OL/OFF status button. This avoids
    OCRing arbitrary app content behind the transparent floating controls.
    """
    status_config = _macos_status_config(config)
    if bool(status_config.get("capture_status_window_button", True)):
        options = status_window_options(config)
        status_width = int(options.width * 0.52)
        pad_x = int(status_config.get("capture_padding_x", _STATUS_BUTTON_PADDING_X))
        pad_y = int(status_config.get("capture_padding_y", _STATUS_BUTTON_PADDING_Y))
        x = int(screen_width - options.margin_right - options.width - pad_x)
        y = int(options.margin_top - pad_y)
        region_width = status_width + pad_x * 2
        region_height = int(options.height) + pad_y * 2
        x = max(0, min(int(screen_width) - 1, x))
        y = max(0, y)
        region_width = max(1, min(region_width, int(screen_width) - x))
        return x, y, region_width, region_height

    width = int(status_config.get("capture_width", _CAPTURE_WIDTH))
    height = int(status_config.get("capture_height", _MENU_BAR_HEIGHT))
    width = max(120, min(int(screen_width), width))
    height = max(20, min(320, height))
    x = max(0, int(screen_width) - width)
    return x, 0, width, height


def _status_window_button_rect(config: dict[str, Any], image_width: int, image_height: int) -> tuple[int, int, int, int] | None:
    """Return expected OL/OFF button rect inside the captured status screenshot."""
    options = status_window_options(config)
    status_config = _macos_status_config(config)
    status_width = int(options.width * 0.52)
    if bool(status_config.get("capture_status_window_button", True)):
        pad_x = int(status_config.get("capture_padding_x", _STATUS_BUTTON_PADDING_X))
        pad_y = int(status_config.get("capture_padding_y", _STATUS_BUTTON_PADDING_Y))
        logical_width = max(1, status_width + pad_x * 2)
        logical_height = max(1, int(options.height) + pad_y * 2)
        scale_x = image_width / logical_width
        scale_y = image_height / logical_height
        x = int(pad_x * scale_x)
        y = int(pad_y * scale_y)
        w = int(status_width * scale_x)
        h = int(options.height * scale_y)
        return x, y, min(image_width - x, w), min(image_height - y, h)

    logical_width = max(1, int(status_config.get("capture_width", _CAPTURE_WIDTH)))
    logical_height = max(1, int(status_config.get("capture_height", _MENU_BAR_HEIGHT)))
    scale_x = image_width / logical_width
    scale_y = image_height / logical_height
    x = int((logical_width - options.margin_right - options.width) * scale_x)
    y = int(options.margin_top * scale_y)
    w = int(status_width * scale_x)
    h = int(options.height * scale_y)
    if x < 0 or y < 0 or x >= image_width or y >= image_height:
        return None
    x2 = min(image_width, x + w)
    y2 = min(image_height, y + h)
    if x2 <= x or y2 <= y:
        return None
    return x, y, x2 - x, y2 - y


def _classify_status_window_pixels(image_path: str, config: dict[str, Any]) -> tuple[str, str, float]:
    """Classify OL/OFF from the configured status-window button color.

    This is a fallback when OCR cannot read the transparent control reliably.
    It only inspects the expected status button rectangle inside the dedicated
    top-right status capture, not arbitrary app content.
    """
    try:
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
    except Exception as exc:
        LOGGER.debug("MacosStatusDetector: visual status fallback failed to open image: %s", exc)
        return "unknown", "", 0.0

    rect = _status_window_button_rect(config, image.width, image.height)
    if rect is None:
        return "unknown", "", 0.0

    x, y, w, h = rect
    crop = image.crop((x, y, x + w, y + h))
    get_flattened_data = getattr(crop, "get_flattened_data", None)
    pixels = list(get_flattened_data() if get_flattened_data is not None else crop.getdata())
    if not pixels:
        return "unknown", "", 0.0

    green_count = 0
    red_count = 0
    for r, g, b in pixels:
        if g >= 145 and r <= 120 and b <= 150 and g >= max(r, b) * 1.45:
            green_count += 1
        if r >= 145 and g <= 120 and b <= 140 and r >= max(g, b) * 1.45:
            red_count += 1

    area = max(1, len(pixels))
    green_ratio = green_count / area
    red_ratio = red_count / area
    min_pixels = max(30, int(area * 0.006))

    if green_count >= min_pixels and green_count >= red_count * 2.0:
        confidence = min(0.90, 0.65 + green_ratio * 6.0)
        return "active", f"visual_status_window_green pixels={green_count}", confidence
    if red_count >= min_pixels and red_count >= green_count * 2.0:
        confidence = min(0.90, 0.65 + red_ratio * 6.0)
        return "inactive", f"visual_status_window_red pixels={red_count}", confidence
    return "unknown", "", 0.0


def _capture_menu_bar_screenshot(config: dict[str, Any]) -> str | None:
    """Capture the configured status-control region for visual/OCR detection."""
    screenshot_dir = Path(config.get("screenshot_dir", "screenshots"))
    if not screenshot_dir.is_absolute():
        screenshot_dir = Path(__file__).resolve().parents[1] / screenshot_dir
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    output_path = screenshot_dir / (
        f"menu_bar_status_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    )
    try:
        import pyautogui  # type: ignore

        screen_w, _screen_h = pyautogui.size()
        region = _capture_region(int(screen_w), config)
        image = pyautogui.screenshot(region=region)
        image.save(output_path)
        LOGGER.debug(
            "MacosStatusDetector: captured menu bar strip. path=%s region=%s",
            output_path, region,
        )
        return str(output_path)
    except Exception as exc:
        LOGGER.warning(
            "MacosStatusDetector: screenshot failed (Screen Recording permission needed): %s", exc
        )
        return None


def _ocr_screenshot(path: str, config: dict[str, Any]) -> list[str]:
    """OCR the given image and return a list of text strings."""
    try:
        from src.ocr_reader import read_image_text

        items = read_image_text(
            path,
            languages=["en", "ch_sim"],
            min_confidence=0.3,
            preprocess=False,
        )
        return [str(item.get("text", "")).strip() for item in items if item.get("text", "").strip()]
    except Exception as exc:
        LOGGER.warning("MacosStatusDetector: OCR failed: %s", exc)
        return []


def detect_macos_status(
    config: dict[str, Any],
    *,
    capture_func: Callable[[dict[str, Any]], str | None] = _capture_menu_bar_screenshot,
    ocr_func: Callable[[str, dict[str, Any]], list[str]] = _ocr_screenshot,
    now_func: Callable[[], datetime] = datetime.now,
) -> MacosStatusDetection:
    """Capture and OCR/visually classify the status-control region.

    Never raises — all failures return status='unknown' (safe default).
    """
    now = now_func()
    try:
        screenshot_path = capture_func(config)
    except Exception as exc:
        LOGGER.warning("MacosStatusDetector: screenshot callable failed: %s", exc)
        screenshot_path = None

    if not screenshot_path:
        LOGGER.warning("MacosStatusDetector: no screenshot → status=unknown (safe default: no send)")
        return MacosStatusDetection(
            raw_status="unknown",
            db_status="unknown",
            detected_text="",
            screenshot_path=None,
            detected_at=now,
            confidence=0.0,
        )

    raw_status, matched_text, confidence = _classify_status_window_pixels(screenshot_path, config)
    texts: list[str] = []
    if raw_status == "unknown":
        try:
            texts = ocr_func(screenshot_path, config)
        except Exception as exc:
            LOGGER.warning("MacosStatusDetector: OCR callable failed: %s", exc)
            texts = []
        raw_status, matched_text = _classify_text(texts)
        confidence = 0.9 if raw_status != "unknown" else 0.0

    LOGGER.info(
        "MacosStatusDetector: ocr_text_count=%s matched=%r raw_status=%s",
        len(texts), matched_text, raw_status,
    )

    return MacosStatusDetection(
        raw_status=raw_status,
        db_status=_status_to_db_value(raw_status),
        detected_text=matched_text,
        screenshot_path=screenshot_path,
        detected_at=now,
        confidence=confidence,
    )


class MacosStatusWatcher:
    """Polls the macOS menu bar and updates OwnerStatusStore on state change.

    Usage (inside auto-reply daemon):
        watcher = MacosStatusWatcher(config)
        detection = watcher.poll()   # call each daemon tick
    """

    def __init__(
        self,
        config: dict[str, Any],
        *,
        store: OwnerStatusStore | None = None,
        capture_func: Callable[[dict[str, Any]], str | None] = _capture_menu_bar_screenshot,
        ocr_func: Callable[[str, dict[str, Any]], list[str]] = _ocr_screenshot,
        now_func: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.config = config
        self.store = store or OwnerStatusStore(config.get("database_path"))
        self.capture_func = capture_func
        self.ocr_func = ocr_func
        self.now_func = now_func
        self._last_raw_status: str | None = None

    def close(self) -> None:
        try:
            self.store.close()
        except Exception:
            pass

    def poll(self) -> MacosStatusDetection:
        """Run one detection pass.  If status changed, update DB and log the transition."""
        detection = detect_macos_status(
            self.config,
            capture_func=self.capture_func,
            ocr_func=self.ocr_func,
            now_func=self.now_func,
        )

        if detection.raw_status == "unknown":
            if self._last_raw_status != "unknown":
                prev = self._last_raw_status or "not yet read"
                LOGGER.warning(
                    "MacosStatusWatcher: STATUS CHANGED %s → unknown. "
                    "Auto-reply will NOT send (safe default). screenshot=%s",
                    prev,
                    detection.screenshot_path,
                )
            LOGGER.warning(
                "MacosStatusWatcher: status=unknown — cannot read OL/OFF status control. "
                "Auto-reply will NOT send (safe default). screenshot=%s",
                detection.screenshot_path,
            )
            self._last_raw_status = "unknown"
            return detection

        if detection.raw_status != self._last_raw_status:
            prev = self._last_raw_status or "not yet read"
            LOGGER.info(
                "MacosStatusWatcher: STATUS CHANGED %s → %s (matched=%r) — updating database.",
                prev, detection.raw_status, detection.detected_text,
            )
            try:
                db_value = detection.db_status
                validate_owner_status(db_value)
                self.store.set_status(
                    db_value,
                    updated_by="macos_status_detector",
                    note=f"auto-detected: {detection.detected_text!r}",
                    now=detection.detected_at,
                )
                LOGGER.info(
                    "MacosStatusWatcher: DB updated → owner_status=%s  "
                    "(OL=owner-online=blocked / OFF=owner-offline=auto-reply-eligible)",
                    db_value,
                )
            except Exception as exc:
                LOGGER.error("MacosStatusWatcher: DB update failed: %s", exc)

        self._last_raw_status = detection.raw_status
        return detection
