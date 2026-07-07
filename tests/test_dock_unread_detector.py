from pathlib import Path

from PIL import Image, ImageDraw

from src.dock_unread_detector import (
    analyze_dock_screenshot,
    detect_dock_wechat_unread,
    dock_unread_config,
)


def make_config(tmp_path: Path, **overrides):
    dock = {
        "enabled": True,
        "require_for_auto_reply": True,
        "capture_bottom_pixels": 220,
        "debug_screenshot_dir": str(tmp_path),
        "min_confidence": 0.55,
        "min_red_badge_side": 6,
        "max_red_badge_side": 64,
        "min_green_icon_side": 24,
        "max_green_icon_side": 140,
    }
    dock.update(overrides)
    return {"dock_unread": dock}


def write_dock_fixture(path: Path, *, green_icon=True, red_badge=True, unrelated_red=False):
    image = Image.new("RGB", (900, 220), (242, 242, 242))
    draw = ImageDraw.Draw(image)
    if green_icon:
        draw.rounded_rectangle((390, 92, 462, 164), radius=16, fill=(28, 176, 40))
    if red_badge:
        draw.ellipse((443, 82, 471, 110), fill=(230, 38, 40))
        draw.line((457, 88, 457, 104), fill=(255, 255, 255), width=3)
    if unrelated_red:
        draw.ellipse((110, 88, 138, 116), fill=(230, 38, 40))
    image.save(path)


def test_dock_config_missing_defaults_to_disabled():
    config = dock_unread_config({})

    assert config["enabled"] is False
    assert config["require_for_auto_reply"] is False


def test_wechat_green_icon_with_attached_red_badge_is_unread(tmp_path: Path):
    path = tmp_path / "dock.png"
    write_dock_fixture(path, green_icon=True, red_badge=True)

    detection = analyze_dock_screenshot(path, make_config(tmp_path))

    assert detection.ok is True
    assert detection.has_unread is True
    assert detection.confidence >= 0.55
    assert len(detection.wechat_icon_candidates) >= 1
    assert len(detection.red_badge_candidates) >= 1
    assert detection.associated_badges
    assert detection.green_mask_path
    assert detection.red_mask_path
    assert detection.overlay_path


def test_wechat_green_icon_without_red_badge_is_not_unread(tmp_path: Path):
    path = tmp_path / "dock.png"
    write_dock_fixture(path, green_icon=True, red_badge=False)

    detection = analyze_dock_screenshot(path, make_config(tmp_path))

    assert detection.ok is True
    assert detection.has_unread is False


def test_unrelated_red_badge_without_wechat_icon_is_unknown(tmp_path: Path):
    path = tmp_path / "dock.png"
    write_dock_fixture(path, green_icon=False, red_badge=False, unrelated_red=True)

    detection = analyze_dock_screenshot(path, make_config(tmp_path))

    assert detection.ok is False
    assert detection.has_unread is None
    assert "not confidently found" in detection.message


def test_red_badge_not_attached_to_wechat_icon_is_not_unread(tmp_path: Path):
    path = tmp_path / "dock.png"
    write_dock_fixture(path, green_icon=True, red_badge=False, unrelated_red=True)

    detection = analyze_dock_screenshot(path, make_config(tmp_path))

    assert detection.ok is True
    assert detection.has_unread is False
    assert detection.associated_badges == ()


def test_detect_dock_wechat_unread_disabled_does_not_capture():
    calls = []

    detection = detect_dock_wechat_unread(
        {"dock_unread": {"enabled": False}},
        capture_func=lambda config: calls.append("capture") or "never.png",
    )

    assert detection.ok is False
    assert detection.has_unread is None
    assert calls == []


def test_detect_dock_wechat_unread_capture_failure_is_safe(tmp_path: Path):
    detection = detect_dock_wechat_unread(
        make_config(tmp_path),
        capture_func=lambda config: None,
    )

    assert detection.ok is False
    assert detection.has_unread is None
    assert "unavailable" in detection.message
