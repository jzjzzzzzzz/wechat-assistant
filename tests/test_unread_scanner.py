from datetime import datetime

from PIL import Image, ImageDraw

from src.unread_scanner import (
    UnreadBadge,
    _associate_badges_with_ocr_rows,
    detect_unread_badges,
    scan_unread_events,
)
from src.wechat_screenshot_verifier import ScreenshotVerification
from src.window_capture import WindowCaptureResult
from src.window_locator import WeChatWindow, WindowBounds, WindowLocatorResult


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


def make_config(**background_overrides):
    background_scan = {
        "enabled": True,
        "prefer_background_capture": True,
        "allow_activate_wechat_fallback": False,
        "require_screenshot_verification": True,
        "verifier_min_confidence": 0.70,
        "debug_screenshot_dir": "screenshots/background_scan",
        "max_scan_interval_seconds": 30,
    }
    background_scan.update(background_overrides)
    return {
        "wechat_app_name": "WeChat",
        "screenshot_dir": "screenshots",
        "ocr_confidence_threshold": 0.3,
        "background_scan": background_scan,
        "auto_reply": {
            "min_ocr_confidence": 0.65,
            "blocklist_keywords": ["群", "群聊", "服务通知", "订阅号", "公众号", "微信支付", "微信团队"],
        },
    }


def make_window():
    return WeChatWindow(
        window_id=42,
        owner_name="WeChat",
        window_title="Weixin",
        bounds=WindowBounds(10, 20, 900, 700),
        is_visible=True,
        is_minimized_or_hidden=False,
    )


def make_locator_result(ok=True):
    return WindowLocatorResult(ok, [make_window()] if ok else [], "ok" if ok else "No visible WeChat window found.")


class FakeVerifier:
    def __init__(self, *, min_confidence=0.7, ok=True):
        self.min_confidence = min_confidence
        self.ok = ok

    def verify_image(self, image_path, *, ocr_func=None):
        return ScreenshotVerification(
            ok=self.ok,
            confidence=0.88 if self.ok else 0.2,
            reason="likely WeChat screenshot" if self.ok else "not WeChat",
            cues=["wechat_text:微信"] if self.ok else ["negative_text:Terminal"],
        )


def test_background_unread_scanner_detects_private_unread_candidate_from_mock_ocr():
    calls = []
    items = [
        {"text": "微信", "confidence": 0.95},
        {"text": "Alice", "confidence": 0.92},
        {"text": "未读 1 条", "confidence": 0.9},
    ]

    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: calls.append("locate") or make_locator_result(),
        window_capture_func=lambda window, config: calls.append("capture")
        or WindowCaptureResult(True, "wechat.png", "visible_region", "ok"),
        verifier_factory=lambda **kwargs: FakeVerifier(ok=True),
        ocr_func=lambda path, **kwargs: calls.append(f"ocr:{path}") or items,
        now_func=lambda: BASE_TIME,
    )

    assert calls == ["locate", "capture", "ocr:wechat.png"]
    assert len(events) == 1
    assert events[0].source == "unread_chat_scan"
    assert events[0].sender == "Alice"
    assert events[0].message_preview == "未读 1 条"
    assert events[0].confidence >= 0.65


def test_detect_unread_badges_finds_synthetic_red_badge(tmp_path):
    image_path = tmp_path / "wechat.png"
    image = Image.new("RGB", (900, 700), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 80, 700), fill=(235, 235, 235))
    draw.rectangle((80, 0, 360, 700), fill=(246, 246, 246))
    draw.ellipse((305, 118, 331, 144), fill=(235, 75, 67))
    image.save(image_path)

    badges = detect_unread_badges(image_path)

    assert len(badges) == 1
    assert badges[0].confidence >= 0.65


def test_associate_badges_with_nearest_ocr_chat_name_row():
    badges = [UnreadBadge(305, 118, 26, 26, 0.8)]
    ocr_items = [
        {
            "text": "Alice",
            "confidence": 0.91,
            "bbox": [[120, 112], [190, 112], [190, 145], [120, 145]],
        },
        {
            "text": "Bob",
            "confidence": 0.91,
            "bbox": [[120, 212], [180, 212], [180, 245], [120, 245]],
        },
    ]

    candidates = _associate_badges_with_ocr_rows(badges, ocr_items, image_height=700)

    assert candidates == [("Alice", 0.8, "red_unread_badge")]


def test_associate_badges_preserves_numeric_badge_count_from_ocr():
    badges = [UnreadBadge(305, 118, 26, 26, 0.8)]
    ocr_items = [
        {
            "text": "Alice",
            "confidence": 0.91,
            "bbox": [[120, 112], [190, 112], [190, 145], [120, 145]],
        },
        {
            "text": "3",
            "confidence": 0.85,
            "bbox": [[313, 122], [323, 122], [323, 138], [313, 138]],
        },
    ]

    candidates = _associate_badges_with_ocr_rows(badges, ocr_items, image_height=700)

    assert candidates == [("Alice", 0.8, "red_unread_badge:3")]


def test_background_unread_scanner_detects_badge_candidate_without_unread_text():
    items = [
        {"text": "微信", "confidence": 0.95, "bbox": [[20, 20], [80, 20], [80, 50], [20, 50]]},
        {"text": "Alice", "confidence": 0.92, "bbox": [[120, 112], [190, 112], [190, 145], [120, 145]]},
    ]

    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: make_locator_result(),
        window_capture_func=lambda window, config: WindowCaptureResult(True, "wechat.png", "visible_region", "ok"),
        verifier_factory=lambda **kwargs: FakeVerifier(ok=True),
        ocr_func=lambda path, **kwargs: items,
        badge_detector_func=lambda path: [UnreadBadge(305, 118, 26, 26, 0.82)],
        now_func=lambda: BASE_TIME,
    )

    assert len(events) == 1
    assert events[0].sender == "Alice"
    assert events[0].message_preview == "red_unread_badge"


def test_unread_scanner_skips_ocr_if_verification_fails():
    calls = []

    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: make_locator_result(),
        window_capture_func=lambda window, config: WindowCaptureResult(True, "terminal.png", "visible_region", "ok"),
        verifier_factory=lambda **kwargs: FakeVerifier(ok=False),
        ocr_func=lambda path, **kwargs: calls.append("ocr") or [],
    )

    assert events == []
    assert calls == []


def test_unread_scanner_filters_blocklisted_group_candidate():
    items = [
        {"text": "微信", "confidence": 0.95},
        {"text": "同学群", "confidence": 0.92},
        {"text": "未读 2 条", "confidence": 0.9},
    ]

    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: make_locator_result(),
        window_capture_func=lambda window, config: WindowCaptureResult(True, "wechat.png", "visible_region", "ok"),
        verifier_factory=lambda **kwargs: FakeVerifier(ok=True),
        ocr_func=lambda path, **kwargs: items,
    )

    assert events == []


def test_unread_scanner_filters_blocklisted_badge_candidate():
    items = [
        {"text": "同学群", "confidence": 0.92, "bbox": [[120, 112], [190, 112], [190, 145], [120, 145]]},
    ]

    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: make_locator_result(),
        window_capture_func=lambda window, config: WindowCaptureResult(True, "wechat.png", "visible_region", "ok"),
        verifier_factory=lambda **kwargs: FakeVerifier(ok=True),
        ocr_func=lambda path, **kwargs: items,
        badge_detector_func=lambda path: [UnreadBadge(305, 118, 26, 26, 0.82)],
    )

    assert events == []


def test_unread_scanner_skips_when_window_not_found():
    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: WindowLocatorResult(False, [], "WeChat window not found."),
        window_capture_func=lambda window, config: WindowCaptureResult(True, "wechat.png", "visible_region", "ok"),
        verifier_factory=lambda **kwargs: FakeVerifier(ok=True),
        ocr_func=lambda path, **kwargs: [{"text": "Alice", "confidence": 1.0}],
    )

    assert events == []


def test_activation_fallback_is_disabled_by_default():
    calls = []

    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: WindowLocatorResult(False, [], "WeChat window not found."),
        activate_func=lambda *args, **kwargs: calls.append("activate") or True,
    )

    assert events == []
    assert calls == []


def test_activation_fallback_runs_only_when_explicitly_enabled():
    calls = []
    items = [
        {"text": "Alice", "confidence": 0.92},
        {"text": "未读 1 条", "confidence": 0.9},
    ]

    events = scan_unread_events(
        make_config(allow_activate_wechat_fallback=True),
        locator_func=lambda **kwargs: WindowLocatorResult(False, [], "WeChat window not found."),
        activate_func=lambda *args, **kwargs: calls.append("activate") or True,
        frontmost_func=lambda app_name: True,
        capture_func=lambda config: calls.append("capture") or "legacy.png",
        ocr_func=lambda path, **kwargs: items,
        now_func=lambda: BASE_TIME,
    )

    assert calls == ["activate", "capture"]
    assert len(events) == 1
    assert events[0].sender == "Alice"
