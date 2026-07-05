from datetime import datetime

from src.unread_scanner import scan_unread_events
from src.wechat_window import UiActionResult


def make_config():
    return {
        "wechat_app_name": "WeChat",
        "screenshot_dir": "screenshots",
        "auto_reply": {
            "min_ocr_confidence": 0.65,
            "blocklist_keywords": ["群", "服务通知", "订阅号", "公众号"],
        },
    }


def test_unread_scanner_detects_private_unread_candidate_from_mock_ocr():
    items = [
        {"text": "Alice", "confidence": 0.92},
        {"text": "未读 1 条", "confidence": 0.9},
    ]

    events = scan_unread_events(
        make_config(),
        activate_func=lambda *args, **kwargs: UiActionResult("activate_wechat", True, "ok"),
        frontmost_func=lambda app_name: True,
        capture_func=lambda config: "chat-list.png",
        ocr_func=lambda path, **kwargs: items,
        now_func=lambda: datetime(2026, 7, 5, 12, 0, 0),
    )

    assert len(events) == 1
    assert events[0].source == "unread_chat_scan"
    assert events[0].sender == "Alice"
    assert events[0].confidence == 0.9


def test_unread_scanner_ignores_standalone_numeric_text_without_visual_badge_detector():
    items = [
        {"text": "Alice", "confidence": 0.92},
        {"text": "2", "confidence": 0.9},
    ]

    events = scan_unread_events(
        make_config(),
        activate_func=lambda *args, **kwargs: UiActionResult("activate_wechat", True, "ok"),
        frontmost_func=lambda app_name: True,
        capture_func=lambda config: "chat-list.png",
        ocr_func=lambda path, **kwargs: items,
    )

    assert events == []


def test_unread_scanner_ignores_generic_ocr_text_that_is_not_unread_marker():
    items = [
        {"text": "notification", "confidence": 1.0},
        {"text": "unread-scan", "confidence": 0.99},
        {"text": "candidates.", "confidence": 0.96},
    ]

    events = scan_unread_events(
        make_config(),
        activate_func=lambda *args, **kwargs: UiActionResult("activate_wechat", True, "ok"),
        frontmost_func=lambda app_name: True,
        capture_func=lambda config: "chat-list.png",
        ocr_func=lambda path, **kwargs: items,
    )

    assert events == []


def test_unread_scanner_filters_blocklisted_group_candidate():
    items = [
        {"text": "同学群", "confidence": 0.92},
        {"text": "未读 2 条", "confidence": 0.9},
    ]

    events = scan_unread_events(
        make_config(),
        activate_func=lambda *args, **kwargs: UiActionResult("activate_wechat", True, "ok"),
        frontmost_func=lambda app_name: True,
        capture_func=lambda config: "chat-list.png",
        ocr_func=lambda path, **kwargs: items,
    )

    assert events == []


def test_unread_scanner_fails_safely_when_activation_fails():
    events = scan_unread_events(
        make_config(),
        activate_func=lambda *args, **kwargs: UiActionResult("activate_wechat", False, "permission denied"),
        frontmost_func=lambda app_name: True,
        capture_func=lambda config: "chat-list.png",
        ocr_func=lambda path, **kwargs: [{"text": "Alice", "confidence": 1.0}],
    )

    assert events == []


def test_unread_scanner_fails_safely_when_wechat_is_not_frontmost():
    events = scan_unread_events(
        make_config(),
        activate_func=lambda *args, **kwargs: UiActionResult("activate_wechat", True, "ok"),
        frontmost_func=lambda app_name: False,
        capture_func=lambda config: "chat-list.png",
        ocr_func=lambda path, **kwargs: [{"text": "Alice", "confidence": 1.0}],
    )

    assert events == []
