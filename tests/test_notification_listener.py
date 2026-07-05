from datetime import datetime

from src.notification_listener import detect_notification_events


def make_config():
    return {
        "screenshot_dir": "screenshots",
        "auto_reply": {
            "min_ocr_confidence": 0.65,
            "blocklist_keywords": ["群", "服务通知", "公众号"],
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
