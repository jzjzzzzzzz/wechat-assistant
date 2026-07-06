from datetime import datetime

from src.notification_listener import _notification_capture_region, detect_notification_events


def make_config():
    return {
        "screenshot_dir": "screenshots",
        "auto_reply": {
            "min_ocr_confidence": 0.65,
            "require_private_chat_whitelist": True,
            "private_chat_whitelist": ["爱", "Alice"],
            "blocklist_keywords": ["群", "服务通知", "公众号"],
            "non_private_keywords": ["Official Accounts", "Service Accounts", "公众号"],
        },
        "notification_ocr": {
            "skip_menu_bar_pixels": 28,
            "capture_width": 520,
            "capture_height": 360,
            "menu_bar_noise_texts": ["OL", "OFF", "iBar"],
        },
    }


def test_notification_listener_detects_wechat_candidate_from_mock_ocr():
    items = [
        {"text": "微信", "confidence": 0.9},
        {"text": "Alice", "confidence": 0.88},
        {"text": "hello", "confidence": 0.8},
    ]

    events = detect_notification_events(
        make_config(),
        capture_func=lambda config: "notification.png",
        ocr_func=lambda path, **kwargs: items,
        now_func=lambda: datetime(2026, 7, 5, 12, 0, 0),
    )

    assert len(events) == 1
    assert events[0].source == "notification_ocr"
    assert events[0].sender == "Alice"
    assert events[0].message_preview == "hello"
    assert events[0].confidence == 0.9


def test_notification_listener_ignores_status_menu_ocr_noise():
    items = [
        {"text": "🟢 OL", "confidence": 0.9},
        {"text": "iBar", "confidence": 0.9},
        {"text": "微信", "confidence": 0.9},
        {"text": "Alice", "confidence": 0.88},
        {"text": "hello", "confidence": 0.8},
        {"text": "OFF", "confidence": 0.8},
    ]

    events = detect_notification_events(
        make_config(),
        capture_func=lambda config: "notification.png",
        ocr_func=lambda path, **kwargs: items,
        now_func=lambda: datetime(2026, 7, 5, 12, 0, 0),
    )

    assert len(events) == 1
    assert events[0].sender == "Alice"
    assert events[0].message_preview == "hello"


def test_notification_capture_region_skips_menu_bar_by_default():
    region = _notification_capture_region(1760, 1280, make_config())

    assert region == (1240, 28, 520, 360)


def test_notification_capture_region_can_disable_menu_bar_skip():
    config = make_config()
    config["notification_ocr"]["skip_menu_bar_pixels"] = 0

    region = _notification_capture_region(1760, 1280, config)

    assert region == (1240, 0, 520, 360)


def test_notification_listener_ignores_low_confidence_candidate():
    items = [
        {"text": "微信", "confidence": 0.5},
        {"text": "Alice", "confidence": 0.5},
    ]

    events = detect_notification_events(
        make_config(),
        capture_func=lambda config: "notification.png",
        ocr_func=lambda path, **kwargs: items,
    )

    assert events == []


def test_notification_listener_is_safe_when_screenshot_fails():
    events = detect_notification_events(
        make_config(),
        capture_func=lambda config: None,
        ocr_func=lambda path, **kwargs: [{"text": "微信", "confidence": 1.0}],
    )

    assert events == []


def test_notification_listener_ignores_non_wechat_ocr_text():
    events = detect_notification_events(
        make_config(),
        capture_func=lambda config: "notification.png",
        ocr_func=lambda path, **kwargs: [{"text": "Calendar", "confidence": 0.99}],
    )

    assert events == []


def test_notification_listener_ignores_sender_outside_private_whitelist():
    items = [
        {"text": "微信", "confidence": 0.9},
        {"text": "Mallory", "confidence": 0.88},
        {"text": "hello", "confidence": 0.8},
    ]

    events = detect_notification_events(
        make_config(),
        capture_func=lambda config: "notification.png",
        ocr_func=lambda path, **kwargs: items,
    )

    assert events == []
