"""Realtime macOS top-right corner status detection via OCR.

Reads the macOS menu bar region (top-right corner) and maps the
WeChat Assistant status label to a system status value:

  Screen shows "OL" / "Online" / "WA ONLINE" → status = "active"
  Screen shows "OFF" / "Offline" / "WA OFFLINE" → status = "inactive"
  Unreadable / ambiguous → status = "unknown"  (safe default: no send)

The detector is used by the auto-reply daemon to keep the project
database in sync with whatever the user has set on the status menu
(rumps menu bar app).  Every state transition is logged.

Terminology note — "active" vs "online":
  The OwnerStatusStore stores "online" / "offline" (legacy keys, unchanged).
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


LOGGER = logging.getLogger(__name__)

# Pixels from the top of the screen to capture (macOS menu bar height ≈ 24-28 px).
_MENU_BAR_HEIGHT = 30
# Width of the menu-bar strip to inspect for status labels.
_CAPTURE_WIDTH = 1400

# Text tokens that indicate the system is ACTIVE (OL / Online).
_ONLINE_TOKENS: frozenset[str] = frozenset({
    "OL",
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
    """Result of one top-right corner status scan."""

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
    return re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]+", stripped)


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


def _capture_region(screen_width: int, config: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return the top-right menu-bar region used for status OCR.

    We capture a wide but shallow strip. It stays within the macOS menu bar
    instead of OCRing app content, while giving iBar enough room to place the
    short "OL"/"OFF" status item away from the clock.
    """
    status_config = config.get("macos_status", {})
    if not isinstance(status_config, dict):
        status_config = {}
    width = int(status_config.get("capture_width", _CAPTURE_WIDTH))
    height = int(status_config.get("capture_height", _MENU_BAR_HEIGHT))
    width = max(120, min(int(screen_width), width))
    height = max(20, min(60, height))
    x = max(0, int(screen_width) - width)
    return x, 0, width, height


def _capture_menu_bar_screenshot(config: dict[str, Any]) -> str | None:
    """Capture a narrow strip of the top-right menu bar for OCR."""
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
    """Capture and OCR the top-right menu bar; return current status detection.

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

    try:
        texts = ocr_func(screenshot_path, config)
    except Exception as exc:
        LOGGER.warning("MacosStatusDetector: OCR callable failed: %s", exc)
        texts = []
    raw_status, matched_text = _classify_text(texts)

    LOGGER.info(
        "MacosStatusDetector: ocr_texts=%r matched=%r raw_status=%s",
        texts, matched_text, raw_status,
    )

    return MacosStatusDetection(
        raw_status=raw_status,
        db_status=_status_to_db_value(raw_status),
        detected_text=matched_text,
        screenshot_path=screenshot_path,
        detected_at=now,
        confidence=0.9 if raw_status != "unknown" else 0.0,
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
                "MacosStatusWatcher: status=unknown — cannot read top-right corner. "
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
                    "(OL=active=auto-reply-allowed / OFF=inactive=blocked)",
                    db_value,
                )
            except Exception as exc:
                LOGGER.error("MacosStatusWatcher: DB update failed: %s", exc)

        self._last_raw_status = detection.raw_status
        return detection
