"""OCR helpers based on EasyOCR."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.screenshot import latest_screenshot


LOGGER = logging.getLogger(__name__)


def read_image_text(
    image_path: str | Path,
    languages: list[str] | None = None,
    *,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    languages = languages or ["ch_sim", "en"]
    path = Path(image_path)
    if not path.exists():
        LOGGER.error("OCR image does not exist: %s", path)
        return []

    try:
        import easyocr  # type: ignore

        reader = easyocr.Reader(languages, gpu=False)
        raw_results = reader.readtext(str(path))
    except Exception as exc:  # pragma: no cover - depends on OCR runtime/model
        LOGGER.error("OCR failed for %s: %s", path, exc)
        return []

    results: list[dict[str, Any]] = []
    for _bbox, text, confidence in raw_results:
        cleaned = str(text).strip()
        confidence = float(confidence)
        if cleaned and confidence >= min_confidence:
            results.append(
                {
                    "text": cleaned,
                    "confidence": confidence,
                    "source": str(path),
                }
            )
    LOGGER.info("OCR read %s text item(s) from %s", len(results), path)
    return results


def read_latest_screenshot_text(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = latest_screenshot(config)
    if path is None:
        LOGGER.warning("No screenshot found for OCR.")
        return []
    return read_image_text(path, min_confidence=float(config.get("ocr_confidence_threshold", 0.0)))
