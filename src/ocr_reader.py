"""OCR helpers based on EasyOCR."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Iterable

from src.screenshot import latest_screenshot


LOGGER = logging.getLogger(__name__)
_READER_CACHE: dict[tuple[tuple[str, ...], bool, int], Any] = {}


def _get_reader(languages: list[str], *, gpu: bool = False) -> Any:
    import easyocr  # type: ignore

    key = (tuple(languages), gpu, id(easyocr.Reader))
    reader = _READER_CACHE.get(key)
    if reader is None:
        reader = easyocr.Reader(languages, gpu=gpu)
        _READER_CACHE[key] = reader
    return reader


def _normalize_bbox(bbox: Any) -> list[list[float]] | None:
    if not bbox:
        return None
    try:
        return [[float(point[0]), float(point[1])] for point in bbox]
    except Exception:
        return None


def _dedupe_key(text: str, bbox: Any) -> tuple[str, tuple[int, ...] | None]:
    normalized_text = " ".join(text.casefold().split())
    normalized_bbox = _normalize_bbox(bbox)
    if normalized_bbox is None:
        return normalized_text, None
    flattened = tuple(round(value / 4) for point in normalized_bbox for value in point)
    return normalized_text, flattened


def _preprocessed_image_paths(path: Path, *, enabled: bool = True) -> Iterable[tuple[str, Path]]:
    """Yield OCR input variants tuned for small WeChat UI text."""
    yield "original", path
    if not enabled:
        return

    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except Exception as exc:  # pragma: no cover - pillow is a runtime dependency
        LOGGER.warning("OCR preprocessing disabled; Pillow unavailable: %s", exc)
        return

    with tempfile.TemporaryDirectory(prefix="wechat_ocr_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        try:
            with Image.open(path) as image:
                rgb = image.convert("RGB")
                scale = 2 if max(rgb.size) < 3000 else 1
                if scale > 1:
                    resized = rgb.resize((rgb.width * scale, rgb.height * scale), Image.Resampling.LANCZOS)
                else:
                    resized = rgb.copy()

                gray = ImageOps.grayscale(resized)
                enhanced = ImageEnhance.Contrast(gray).enhance(1.8)
                sharpened = enhanced.filter(ImageFilter.SHARPEN)
                binary = sharpened.point(lambda px: 255 if px > 175 else 0)

                variants = {
                    "gray_enhanced": sharpened,
                    "binary": binary,
                }
                for name, variant in variants.items():
                    variant_path = tmp_path / f"{path.stem}_{name}.png"
                    variant.save(variant_path)
                    yield name, variant_path
        except Exception as exc:
            LOGGER.warning("OCR preprocessing failed for %s: %s", path, exc)
            return


def read_image_text(
    image_path: str | Path,
    languages: list[str] | None = None,
    *,
    min_confidence: float = 0.0,
    preprocess: bool = True,
) -> list[dict[str, Any]]:
    languages = languages or ["ch_sim", "en"]
    path = Path(image_path)
    if not path.exists():
        LOGGER.error("OCR image does not exist: %s", path)
        return []

    try:
        reader = _get_reader(languages, gpu=False)
    except Exception as exc:  # pragma: no cover - depends on OCR runtime/model
        LOGGER.error("OCR reader initialization failed for %s: %s", path, exc)
        return []

    by_key: dict[tuple[str, tuple[int, ...] | None], dict[str, Any]] = {}
    for variant, variant_path in _preprocessed_image_paths(path, enabled=preprocess):
        try:
            raw_results = reader.readtext(str(variant_path))
        except Exception as exc:  # pragma: no cover - depends on OCR runtime/model
            LOGGER.warning("OCR failed for %s variant=%s: %s", path, variant, exc)
            continue

        for bbox, text, confidence in raw_results:
            cleaned = str(text).strip()
            confidence = float(confidence)
            if not cleaned or confidence < min_confidence:
                continue

            key = _dedupe_key(cleaned, bbox)
            item = {
                "text": cleaned,
                "confidence": confidence,
                "source": str(path),
                "variant": variant,
            }
            normalized_bbox = _normalize_bbox(bbox)
            if normalized_bbox is not None:
                item["bbox"] = normalized_bbox

            existing = by_key.get(key)
            if existing is None or confidence > float(existing["confidence"]):
                by_key[key] = item

    results = sorted(by_key.values(), key=lambda item: float(item["confidence"]), reverse=True)
    LOGGER.info("OCR read %s text item(s) from %s", len(results), path)
    return results


def read_latest_screenshot_text(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = latest_screenshot(config)
    if path is None:
        LOGGER.warning("No screenshot found for OCR.")
        return []
    return read_image_text(path, min_confidence=float(config.get("ocr_confidence_threshold", 0.0)))
