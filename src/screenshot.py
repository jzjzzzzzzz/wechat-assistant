"""Screenshot capture helpers."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


def capture_screenshot(config: dict[str, Any] | None = None) -> str | None:
    config = config or {}
    screenshot_dir = Path(config.get("screenshot_dir", "screenshots"))
    if not screenshot_dir.is_absolute():
        screenshot_dir = PROJECT_ROOT / screenshot_dir
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = screenshot_dir / f"screenshot_{timestamp}.png"

    try:
        import pyautogui  # type: ignore

        image = pyautogui.screenshot()
        image.save(output_path)
        LOGGER.info("Screenshot saved: %s", output_path)
        return str(output_path)
    except Exception as exc:  # pragma: no cover - permission dependent
        LOGGER.error(
            "Screenshot failed. Enable System Settings > Privacy & Security > "
            "Screen Recording for your terminal. Error: %s",
            exc,
        )
        return None


def latest_screenshot(config: dict[str, Any] | None = None) -> Path | None:
    config = config or {}
    screenshot_dir = Path(config.get("screenshot_dir", "screenshots"))
    if not screenshot_dir.is_absolute():
        screenshot_dir = PROJECT_ROOT / screenshot_dir
    if not screenshot_dir.exists():
        return None
    screenshots = sorted(screenshot_dir.glob("*.png"), key=lambda path: path.stat().st_mtime)
    return screenshots[-1] if screenshots else None
