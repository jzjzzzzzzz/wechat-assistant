"""OpenCV helpers for visible UI template detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass(frozen=True)
class TemplateMatch:
    template_name: str
    ok: bool
    confidence: float
    threshold: float
    bounding_box: BoundingBox | None
    image_path: str
    template_path: str
    debug_output_path: str | None = None
    message: str = ""


def _validate_threshold(threshold: float) -> float:
    value = float(threshold)
    if not 0.0 <= value <= 1.0:
        raise ValueError("template matching threshold must be between 0 and 1")
    return value


def match_template(
    image_path: str | Path,
    template_path: str | Path,
    *,
    threshold: float = 0.85,
    template_name: str | None = None,
    debug_output_path: str | Path | None = None,
) -> TemplateMatch:
    threshold = _validate_threshold(threshold)
    image_path = Path(image_path)
    template_path = Path(template_path)
    name = template_name or template_path.stem

    try:
        import cv2  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local install
        message = f"OpenCV import failed: {exc}"
        LOGGER.error(message)
        return TemplateMatch(name, False, 0.0, threshold, None, str(image_path), str(template_path), message=message)

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if image is None:
        message = f"Could not load image: {image_path}"
        LOGGER.error(message)
        return TemplateMatch(name, False, 0.0, threshold, None, str(image_path), str(template_path), message=message)
    if template is None:
        message = f"Could not load template: {template_path}"
        LOGGER.error(message)
        return TemplateMatch(name, False, 0.0, threshold, None, str(image_path), str(template_path), message=message)

    image_height, image_width = image.shape[:2]
    template_height, template_width = template.shape[:2]
    if template_width > image_width or template_height > image_height:
        message = "Template is larger than image."
        LOGGER.warning(message)
        return TemplateMatch(name, False, 0.0, threshold, None, str(image_path), str(template_path), message=message)

    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(image_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    _min_value, max_value, _min_location, max_location = cv2.minMaxLoc(result)
    confidence = float(max_value)
    bounding_box = BoundingBox(max_location[0], max_location[1], template_width, template_height)
    ok = confidence >= threshold

    debug_path: str | None = None
    if debug_output_path is not None:
        debug_path = str(debug_output_path)
        debug_target = Path(debug_path)
        debug_target.parent.mkdir(parents=True, exist_ok=True)
        overlay = image.copy()
        color = (0, 255, 0) if ok else (0, 0, 255)
        cv2.rectangle(
            overlay,
            (bounding_box.x, bounding_box.y),
            (bounding_box.x + bounding_box.width, bounding_box.y + bounding_box.height),
            color,
            2,
        )
        cv2.imwrite(str(debug_target), overlay)

    message = "Template matched." if ok else "Template confidence below threshold."
    LOGGER.info(
        "Template match template=%s ok=%s confidence=%.4f threshold=%.4f box=%s",
        name,
        ok,
        confidence,
        threshold,
        bounding_box,
    )
    return TemplateMatch(
        template_name=name,
        ok=ok,
        confidence=confidence,
        threshold=threshold,
        bounding_box=bounding_box if ok else None,
        image_path=str(image_path),
        template_path=str(template_path),
        debug_output_path=debug_path,
        message=message,
    )
