from pathlib import Path

import cv2
import numpy as np
import pytest

from src.vision import BoundingBox, match_template


def _write_image(path: Path, image: np.ndarray) -> None:
    assert cv2.imwrite(str(path), image)


def _pattern_a() -> np.ndarray:
    template = np.zeros((12, 14, 3), dtype=np.uint8)
    template[2:10, 3:11] = (255, 255, 255)
    template[4:8, 5:9] = (0, 0, 0)
    template[0, :, :] = (128, 128, 128)
    return template


def _pattern_b() -> np.ndarray:
    template = np.zeros((12, 14, 3), dtype=np.uint8)
    template[:, :, :] = (30, 30, 30)
    template[:, 0:2, :] = (240, 240, 240)
    template[8:12, :, :] = (120, 120, 120)
    return template


def test_match_template_positive_with_synthetic_image(tmp_path: Path) -> None:
    image = np.zeros((80, 90, 3), dtype=np.uint8)
    template = _pattern_a()
    image[25:37, 40:54] = template
    image_path = tmp_path / "screen.png"
    template_path = tmp_path / "template.png"
    _write_image(image_path, image)
    _write_image(template_path, template)

    result = match_template(image_path, template_path, threshold=0.95, template_name="synthetic")

    assert result.ok is True
    assert result.template_name == "synthetic"
    assert result.confidence >= 0.95
    assert result.bounding_box == BoundingBox(x=40, y=25, width=14, height=12)
    assert result.bounding_box.center == (47, 31)


def test_match_template_no_match_below_threshold(tmp_path: Path) -> None:
    image = np.zeros((80, 90, 3), dtype=np.uint8)
    image[25:37, 40:54] = _pattern_a()
    image_path = tmp_path / "screen.png"
    template_path = tmp_path / "missing-template.png"
    _write_image(image_path, image)
    _write_image(template_path, _pattern_b())

    result = match_template(image_path, template_path, threshold=0.99)

    assert result.ok is False
    assert result.bounding_box is None
    assert result.confidence < 0.99


def test_match_template_rejects_invalid_threshold(tmp_path: Path) -> None:
    image_path = tmp_path / "screen.png"
    template_path = tmp_path / "template.png"
    _write_image(image_path, np.zeros((20, 20, 3), dtype=np.uint8))
    _write_image(template_path, _pattern_a())

    with pytest.raises(ValueError):
        match_template(image_path, template_path, threshold=1.1)


def test_match_template_writes_debug_overlay(tmp_path: Path) -> None:
    image = np.zeros((80, 90, 3), dtype=np.uint8)
    template = _pattern_a()
    image[25:37, 40:54] = template
    image_path = tmp_path / "screen.png"
    template_path = tmp_path / "template.png"
    debug_path = tmp_path / "debug" / "overlay.png"
    _write_image(image_path, image)
    _write_image(template_path, template)

    result = match_template(image_path, template_path, threshold=0.95, debug_output_path=debug_path)

    assert result.ok is True
    assert result.debug_output_path == str(debug_path)
    assert debug_path.exists()
