"""OCR-based dual-region verification that the correct contact is open in WeChat.

After search_contact() navigates to a chat, verify_active_contact() crops two
regions from a fresh screenshot and OCR-checks both independently:

  Region 1 — Left sidebar  : the highlighted selected-contact row in the chat list.
  Region 2 — Top title bar : the contact name displayed above the message history.

BOTH regions must contain the target contact name (case-insensitive substring)
for the check to pass.  Requiring two independent sources drastically reduces the
chance of a false positive (e.g. the target name appearing in a message body but
the wrong chat being open).

Typical call site (message_sender.py)::

    from src.contact_verifier import verify_active_contact, ContactVerifyResult

    result = verify_active_contact(config, target, screenshot_func)
    if not result.ok:
        raise RuntimeError(result.message)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.wechat_window import get_wechat_window_rect

LOGGER = logging.getLogger(__name__)

# ── WeChat Mac layout constants (logical pixels) ──────────────────────────────
# These match wechat_window.py's _WECHAT_SIDEBAR_WIDTH.
_SIDEBAR_WIDTH_LOGICAL: int = 240   # total left-panel width (icon strip + contact list)
_TITLE_BAR_HEIGHT_LOGICAL: int = 50   # just the name line at top of chat area
_MACOS_CHROME_HEIGHT_LOGICAL: int = 22  # skip macOS traffic-light chrome

# Well-known aliases for built-in or generic contacts that WeChat may render
# differently on the Mac client. Extend locally as needed.
_DEFAULT_NAME_ALIASES: dict[str, list[str]] = {
    "文件传输助手": ["文件传输助手", "File Transfer"],
    "File Transfer": ["File Transfer", "文件传输助手"],
}


# ── Public data types ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RegionResult:
    """OCR result for a single screen region."""
    name: str             # "sidebar" or "title_bar"
    found: bool
    texts: list[str]
    crop_box: tuple[int, int, int, int] | None  # physical px (x, y, w, h)
    message: str


@dataclass(frozen=True)
class ContactVerifyResult:
    ok: bool
    target: str
    sidebar: RegionResult | None
    title_bar: RegionResult | None
    message: str
    screenshot_path: str | None = None

    def __bool__(self) -> bool:
        return self.ok


# ── Internal helpers ──────────────────────────────────────────────────────────

def _screen_scale_factor(screenshot_path: str) -> float:
    """Compute the physical/logical scale by comparing screenshot size to pyautogui.size()."""
    try:
        import pyautogui  # type: ignore
        from PIL import Image

        logical_w, _ = pyautogui.size()
        with Image.open(screenshot_path) as img:
            physical_w, _ = img.size
        scale = physical_w / logical_w
        LOGGER.debug("Screen scale factor: %.2f (logical_w=%s physical_w=%s)", scale, logical_w, physical_w)
        return scale
    except Exception as exc:
        LOGGER.warning("Could not determine screen scale factor (%s); assuming 2.0", exc)
        return 2.0


def _get_region_boxes(
    window_rect: tuple[int, int, int, int],
    scale: float,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Return (sidebar_box, title_box) as physical-pixel (x, y, w, h) tuples.

    ``window_rect`` is (x, y, width, height) in logical pixels from AppleScript.
    """
    wx, wy, ww, wh = window_rect

    def to_phys(v: int) -> int:
        return round(v * scale)

    # Sidebar: full height of the sidebar panel
    sidebar_box = (
        to_phys(wx),
        to_phys(wy),
        to_phys(_SIDEBAR_WIDTH_LOGICAL),
        to_phys(wh),
    )

    # Title bar: top strip of the main chat area, below macOS window chrome
    title_y = wy + _MACOS_CHROME_HEIGHT_LOGICAL
    title_box = (
        to_phys(wx + _SIDEBAR_WIDTH_LOGICAL),
        to_phys(title_y),
        to_phys(ww - _SIDEBAR_WIDTH_LOGICAL),
        to_phys(_TITLE_BAR_HEIGHT_LOGICAL),
    )

    return sidebar_box, title_box


def _crop_and_ocr(
    screenshot_path: str,
    box: tuple[int, int, int, int],
    config: dict[str, Any],
    region_name: str,
    ocr_func: Callable[[str, dict[str, Any]], list[dict[str, Any]]] | None = None,
) -> list[str]:
    """Crop *box* (physical px x,y,w,h) from *screenshot_path* and return OCR text strings."""
    try:
        from PIL import Image

        x, y, w, h = box
        with Image.open(screenshot_path) as img:
            img_w, img_h = img.size
            # Clamp to image bounds
            x = max(0, min(x, img_w))
            y = max(0, min(y, img_h))
            w = min(w, img_w - x)
            h = min(h, img_h - y)
            if w <= 0 or h <= 0:
                LOGGER.warning("_crop_and_ocr: region %s has zero size after clamping", region_name)
                return []
            crop = img.crop((x, y, x + w, y + h))

        # Save crop to a temp file for EasyOCR (which wants a file path)
        suffix = f"_ocr_region_{region_name}.png"
        tmp_dir = Path(screenshot_path).parent
        tmp_path = tmp_dir / (Path(screenshot_path).stem + suffix)
        crop.save(str(tmp_path))

        runner = ocr_func or ocr_from_path
        results = runner(str(tmp_path), config)
        texts = [str(r.get("text", "")) for r in results]
        LOGGER.info("OCR region '%s' box=%s -> %d text item(s): %s", region_name, box, len(texts), texts)

        try:
            tmp_path.unlink()
        except OSError:
            pass

        return texts
    except Exception as exc:
        LOGGER.error("_crop_and_ocr error for region '%s': %s", region_name, exc)
        return []


def _aliases_for_target(target: str, config: dict[str, Any] | None = None) -> list[str]:
    """Return OCR aliases for *target*.

    Built-in aliases cover WeChat's file-transfer helper. Local one-off OCR
    aliases, such as a specific short contact name being misread, live in
    config["contact_ocr_aliases"] so real contacts are not hard-coded here.
    """
    aliases: list[str] = [target]
    aliases.extend(_DEFAULT_NAME_ALIASES.get(target, []))

    configured = (config or {}).get("contact_ocr_aliases", {})
    if isinstance(configured, dict):
        values = configured.get(target, [])
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            aliases.extend(str(value).strip() for value in values if str(value).strip())

    return list(dict.fromkeys(alias for alias in aliases if alias.strip()))


def _name_in_texts(target: str, texts: list[str], config: dict[str, Any] | None = None) -> bool:
    """Match *target* (and known aliases) against OCR text items.

    Strategy:
    - Exact case-insensitive substring match (always).
    - Fuzzy Levenshtein match only for candidates longer than 3 chars
      (prevents short names from false-matching random text).
      Tolerance: max(1, len // 6), e.g. "File Transfer" (13) → dist ≤ 2.
    """
    candidates = _aliases_for_target(target, config)
    for candidate in candidates:
        c_lower = candidate.strip().lower()
        c_len = len(c_lower)

        for item in texts:
            item_lower = item.strip().lower()
            # Always: exact substring
            if c_lower in item_lower:
                if candidate != target:
                    LOGGER.info(
                        "OCR alias matched target '%s': alias='%s' text='%s'",
                        target,
                        candidate,
                        item,
                    )
                return True
            # Fuzzy only for longer names to avoid short-name false positives.
            if c_len > 3:
                max_dist = max(1, c_len // 6)
                for start in range(max(0, len(item_lower) - c_len + 1)):
                    window = item_lower[start : start + c_len]
                    if len(window) == c_len and _levenshtein(c_lower, window) <= max_dist:
                        LOGGER.debug(
                            "Fuzzy match: '%s' ~ '%s' (dist=%d)",
                            candidate, window, _levenshtein(c_lower, window),
                        )
                        return True
    return False


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def _check_region(
    screenshot_path: str,
    box: tuple[int, int, int, int],
    target: str,
    config: dict[str, Any],
    region_name: str,
    ocr_func: Callable[[str, dict[str, Any]], list[dict[str, Any]]] | None = None,
) -> RegionResult:
    texts = _crop_and_ocr(screenshot_path, box, config, region_name, ocr_func)
    found = _name_in_texts(target, texts, config)
    msg = (
        f"Region '{region_name}': {'PASS' if found else 'FAIL'} "
        f"— '{target}' {'found' if found else 'NOT found'} in {len(texts)} text item(s)."
    )
    LOGGER.info(msg)
    return RegionResult(name=region_name, found=found, texts=texts, crop_box=box, message=msg)


# ── Public API ────────────────────────────────────────────────────────────────

def verify_active_contact(
    config: dict[str, Any],
    target: str,
    screenshot_func: Callable[[dict[str, Any]], str | None],
    ocr_func: Callable[[str, dict[str, Any]], list[dict[str, Any]]] | None = None,
    *,
    retries: int = 2,
    retry_delay: float = 1.0,
) -> ContactVerifyResult:
    """Verify that the WeChat chat for *target* is open by OCR-checking two screen regions.

    Parameters
    ----------
    config:
        Loaded settings dict.
    target:
        Contact display name / remark to find in both the sidebar and the title bar.
    screenshot_func:
        ``(config) -> path | None`` — captures and saves a screenshot.
    ocr_func:
        Optional ``(image_path, config) -> OCR items`` hook used for both cropped
        regions and full-screenshot fallback.
    retries:
        Extra attempts after the first (default 2 → up to 3 total).
    retry_delay:
        Seconds to wait between attempts.
    """
    last_result: ContactVerifyResult | None = None

    for attempt in range(1, retries + 2):
        screenshot_path = screenshot_func(config)
        if screenshot_path is None:
            last_result = ContactVerifyResult(
                ok=False,
                target=target,
                sidebar=None,
                title_bar=None,
                message="Screenshot capture failed; cannot verify active contact.",
                screenshot_path=None,
            )
            LOGGER.warning(
                "verify_active_contact: screenshot failed on attempt %s/%s",
                attempt, retries + 1,
            )
            if attempt <= retries:
                time.sleep(retry_delay)
            continue

        # Determine window rect → crop boxes
        try:
            window_rect = get_wechat_window_rect()
        except Exception as exc:
            LOGGER.warning("Could not get WeChat window rect: %s", exc)
            window_rect = None

        if window_rect is None:
            # Fallback: full-screenshot single-region OCR
            LOGGER.warning(
                "verify_active_contact: window rect unavailable on attempt %s; "
                "falling back to full-screenshot OCR",
                attempt,
            )
            runner = ocr_func or ocr_from_path
            results = runner(screenshot_path, config)
            texts = [str(r.get("text", "")) for r in results]
            found = _name_in_texts(target, texts, config)
            pseudo = RegionResult(
                name="full_screenshot",
                found=found,
                texts=texts,
                crop_box=None,
                message=f"Full-screenshot OCR {'PASS' if found else 'FAIL'}: '{target}'.",
            )
            if found:
                return ContactVerifyResult(
                    ok=True,
                    target=target,
                    sidebar=pseudo,
                    title_bar=pseudo,
                    message=f"Contact verified via full-screenshot OCR on attempt {attempt}.",
                    screenshot_path=screenshot_path,
                )
            last_result = ContactVerifyResult(
                ok=False,
                target=target,
                sidebar=pseudo,
                title_bar=pseudo,
                message=f"Full-screenshot OCR: '{target}' not found. Attempt {attempt}/{retries + 1}.",
                screenshot_path=screenshot_path,
            )
        else:
            scale = _screen_scale_factor(screenshot_path)
            sidebar_box, title_box = _get_region_boxes(window_rect, scale)

            sidebar_result = _check_region(
                screenshot_path, sidebar_box, target, config, "sidebar", ocr_func
            )
            title_result = _check_region(
                screenshot_path, title_box, target, config, "title_bar", ocr_func
            )

            both_pass = sidebar_result.found and title_result.found

            if both_pass:
                msg = (
                    f"Contact verification PASSED (both regions) for '{target}' "
                    f"on attempt {attempt}."
                )
                LOGGER.info(msg)
                return ContactVerifyResult(
                    ok=True,
                    target=target,
                    sidebar=sidebar_result,
                    title_bar=title_result,
                    message=msg,
                    screenshot_path=screenshot_path,
                )

            fail_regions = [r.name for r in (sidebar_result, title_result) if not r.found]
            last_result = ContactVerifyResult(
                ok=False,
                target=target,
                sidebar=sidebar_result,
                title_bar=title_result,
                message=(
                    f"Contact verification FAILED for '{target}' on attempt {attempt}/{retries + 1}. "
                    f"Missing in: {fail_regions}. "
                    f"Sidebar={sidebar_result.found}, TitleBar={title_result.found}."
                ),
                screenshot_path=screenshot_path,
            )
            LOGGER.warning(last_result.message)

        if attempt <= retries:
            time.sleep(retry_delay)

    assert last_result is not None
    LOGGER.error(
        "verify_active_contact: all %s attempt(s) exhausted for target='%s'",
        retries + 1, target,
    )
    return last_result


def ocr_from_path(
    image_path: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Backward-compat shim used by callers that pass ``ocr_func`` explicitly."""
    from src.ocr_reader import read_image_text
    return read_image_text(
        image_path,
        min_confidence=float(config.get("ocr_confidence_threshold", 0.3)),
    )
