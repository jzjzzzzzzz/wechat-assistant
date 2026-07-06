from datetime import datetime

from PIL import Image, ImageDraw

from src.unread_scanner import (
    ChatListRow,
    UnreadBadge,
    _associate_badges_with_ocr_rows,
    associate_badges_with_rows,
    detect_unread_badges,
    detect_unread_badges_with_diagnostics,
    get_last_unread_scan_report,
    segment_chat_list_rows,
    scan_unread_events,
    write_badge_debug_overlay,
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


def test_real_coordinate_chat_list_badge_is_accepted_and_sidebar_badge_rejected(tmp_path):
    image_path = tmp_path / "wechat_full.png"
    image = Image.new("RGB", (1760, 1280), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 110, 1280), fill=(238, 238, 238))
    draw.rectangle((120, 0, 570, 1280), fill=(246, 246, 246))
    draw.ellipse((67, 313, 99, 345), fill=(235, 75, 67))
    draw.ellipse((199, 203, 231, 235), fill=(235, 75, 67))
    draw.line((215, 210, 215, 228), fill="white", width=4)
    image.save(image_path)

    diagnostics = detect_unread_badges_with_diagnostics(image_path)

    assert len(diagnostics.badges) == 1
    badge = diagnostics.badges[0]
    assert 190 <= badge.x <= 205
    assert 198 <= badge.y <= 208
    assert badge.count == 1
    assert any(item.reason == "left_sidebar_or_avatar_region" for item in diagnostics.rejected_contours)
    assert diagnostics.chat_list_crop_path is not None
    assert diagnostics.red_mask_path is not None
    assert diagnostics.contour_overlay_path is not None


def test_window_capture_coordinate_chat_badge_is_accepted_but_nearby_sidebar_badge_rejected(tmp_path):
    image_path = tmp_path / "wechat_window.png"
    image = Image.new("RGB", (1640, 1280), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 110, 1280), fill=(238, 238, 238))
    draw.rectangle((0, 140, 470, 248), fill=(226, 226, 226))
    draw.ellipse((67, 313, 99, 345), fill=(235, 75, 67))
    draw.ellipse((77, 203, 109, 235), fill=(235, 75, 67))
    draw.line((93, 210, 93, 228), fill="white", width=4)
    image.save(image_path)

    diagnostics = detect_unread_badges_with_diagnostics(image_path)

    assert any(70 <= badge.x <= 82 and 198 <= badge.y <= 208 for badge in diagnostics.badges)
    assert any(item.x == 67 and item.reason == "left_sidebar_or_avatar_region" for item in diagnostics.rejected_contours)


def test_tiny_text_like_red_fragments_are_rejected(tmp_path):
    image_path = tmp_path / "wechat_fragments.png"
    image = Image.new("RGB", (1760, 1280), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 0, 570, 1280), fill=(246, 246, 246))
    draw.ellipse((160, 529, 167, 540), fill=(235, 75, 67))
    draw.ellipse((177, 793, 185, 802), fill=(235, 75, 67))
    image.save(image_path)

    diagnostics = detect_unread_badges_with_diagnostics(image_path)

    assert diagnostics.badges == []
    assert any(item.reason in {"likely_text_fragment", "low_circularity"} for item in diagnostics.rejected_contours)


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


def test_segment_chat_list_rows_returns_row_slots_for_synthetic_wechat_image(tmp_path):
    image_path = tmp_path / "wechat.png"
    Image.new("RGB", (900, 700), "white").save(image_path)

    rows = segment_chat_list_rows(image_path)

    assert len(rows) >= 6
    assert rows[0].x > 0
    assert rows[0].width > 200


def test_associate_badges_with_segmented_row_evidence():
    rows = [
        ChatListRow(0, 80, 80, 300, 80),
        ChatListRow(1, 80, 160, 300, 80),
    ]
    badges = [UnreadBadge(305, 178, 26, 26, 0.8)]
    ocr_items = [
        {
            "text": "Alice",
            "confidence": 0.91,
            "bbox": [[120, 92], [190, 92], [190, 125], [120, 125]],
        },
        {
            "text": "Bob",
            "confidence": 0.90,
            "bbox": [[120, 172], [180, 172], [180, 205], [120, 205]],
        },
    ]

    associations = associate_badges_with_rows(badges, rows, ocr_items)

    assert len(associations) == 1
    assert associations[0].sender == "Bob"
    assert "row=1" in associations[0].evidence


def test_write_badge_debug_overlay_saves_row_level_evidence_image(tmp_path):
    image_path = tmp_path / "wechat.png"
    Image.new("RGB", (900, 700), "white").save(image_path)
    row = ChatListRow(0, 80, 80, 300, 80)
    badge = UnreadBadge(305, 98, 26, 26, 0.8)
    association = associate_badges_with_rows(
        [badge],
        [row],
        [
            {
                "text": "Alice",
                "confidence": 0.91,
                "bbox": [[120, 92], [190, 92], [190, 125], [120, 125]],
            }
        ],
    )[0]

    overlay_path = write_badge_debug_overlay(image_path, [row], [badge], [association])

    assert overlay_path is not None
    assert overlay_path.endswith("_badge_overlay.png")
    assert (tmp_path / "wechat_badge_overlay.png").exists()


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


def test_badge_with_row_but_unknown_sender_is_diagnostic_only(tmp_path):
    image_path = tmp_path / "wechat.png"
    Image.new("RGB", (1760, 1280), "white").save(image_path)

    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: make_locator_result(),
        window_capture_func=lambda window, config: WindowCaptureResult(True, str(image_path), "visible_region", "ok"),
        verifier_factory=lambda **kwargs: FakeVerifier(ok=True),
        ocr_func=lambda path, **kwargs: [],
        badge_detector_func=lambda path: [UnreadBadge(199, 203, 32, 32, 0.82, count=1)],
        now_func=lambda: BASE_TIME,
    )

    report = get_last_unread_scan_report()

    assert events == []
    assert report is not None
    assert report.accepted_badge_count == 1
    assert report.association_count == 0
    assert any(reason == "ignored_badge:sender_ocr_failed" for reason in report.ignored_reasons)


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
    report = get_last_unread_scan_report()

    assert events == []
    assert report is not None
    assert any("blocklisted_sender" in reason for reason in report.ignored_reasons)


def test_unread_scanner_filters_english_public_account_badge_candidate():
    items = [
        {"text": "Official Accounts", "confidence": 0.92, "bbox": [[120, 112], [290, 112], [290, 145], [120, 145]]},
    ]

    events = scan_unread_events(
        make_config(),
        locator_func=lambda **kwargs: make_locator_result(),
        window_capture_func=lambda window, config: WindowCaptureResult(True, "wechat.png", "visible_region", "ok"),
        verifier_factory=lambda **kwargs: FakeVerifier(ok=True),
        ocr_func=lambda path, **kwargs: items,
        badge_detector_func=lambda path: [UnreadBadge(305, 118, 26, 26, 0.82)],
    )
    report = get_last_unread_scan_report()

    assert events == []
    assert report is not None
    assert any("non_private_sender_keyword:Official Accounts" in reason for reason in report.ignored_reasons)


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
