from src.config_loader import load_config
from src.wechat_screenshot_verifier import (
    ScreenshotMetadata,
    WeChatScreenshotVerifier,
    should_skip_ocr,
)
from src.window_locator import WindowBounds, WeChatWindow, find_wechat_windows


def test_verifier_accepts_likely_wechat_screenshot_metadata() -> None:
    verifier = WeChatScreenshotVerifier(min_confidence=0.70)
    metadata = ScreenshotMetadata(
        width=1000,
        height=700,
        ocr_texts=["微信", "搜索", "文件传输助手"],
        dominant_left_panel_width_ratio=0.28,
    )

    result = verifier.verify_metadata(metadata)

    assert result.ok is True
    assert result.confidence >= 0.70
    assert should_skip_ocr(result) is False


def test_verifier_rejects_non_wechat_terminal_metadata() -> None:
    verifier = WeChatScreenshotVerifier(min_confidence=0.70)
    metadata = ScreenshotMetadata(
        width=1000,
        height=700,
        ocr_texts=["Terminal", "python -m pytest -q", "zsh"],
        dominant_left_panel_width_ratio=None,
    )

    result = verifier.verify_metadata(metadata)

    assert result.ok is False
    assert should_skip_ocr(result) is True
    assert any(cue.startswith("negative_text:") for cue in result.cues)


def test_verifier_rejects_low_confidence_metadata() -> None:
    verifier = WeChatScreenshotVerifier(min_confidence=0.70)
    metadata = ScreenshotMetadata(width=640, height=480, ocr_texts=["搜索"], dominant_left_panel_width_ratio=None)

    result = verifier.verify_metadata(metadata)

    assert result.ok is False
    assert result.confidence < 0.70


def test_minimized_or_hidden_windows_are_skipped_by_locator() -> None:
    result = find_wechat_windows(
        quartz_records_func=lambda: [
            {
                "kCGWindowOwnerName": "WeChat",
                "kCGWindowName": "Weixin",
                "kCGWindowNumber": 42,
                "kCGWindowBounds": {"X": 10, "Y": 20, "Width": 900, "Height": 700},
                "kCGWindowIsOnscreen": True,
                "is_minimized_or_hidden": True,
            }
        ],
        applescript_records_func=lambda app_name: [],
    )

    assert result.ok is False
    assert result.windows[0].is_minimized_or_hidden is True
    assert result.windows[0].can_attempt_background_capture is False


def test_locator_returns_structured_failure_when_no_wechat_window_found() -> None:
    result = find_wechat_windows(
        quartz_records_func=lambda: [
            {
                "kCGWindowOwnerName": "Terminal",
                "kCGWindowName": "shell",
                "kCGWindowNumber": 7,
                "kCGWindowBounds": {"X": 0, "Y": 0, "Width": 900, "Height": 700},
                "kCGWindowIsOnscreen": True,
            }
        ],
        applescript_records_func=lambda app_name: [],
    )

    assert result.ok is False
    assert result.windows == []
    assert result.message == "No visible WeChat window found."


def test_locator_returns_visible_background_window_without_activation() -> None:
    result = find_wechat_windows(
        quartz_records_func=lambda: [
            {
                "kCGWindowOwnerName": "WeChat",
                "kCGWindowName": "Weixin",
                "kCGWindowNumber": 42,
                "kCGWindowBounds": {"X": 10, "Y": 20, "Width": 900, "Height": 700},
                "kCGWindowIsOnscreen": True,
            }
        ],
        applescript_records_func=lambda app_name: [],
    )

    assert result.ok is True
    assert result.windows[0].window_id == 42
    assert result.windows[0].can_attempt_background_capture is True


def test_locator_prefers_main_wechat_window_over_edit_contact_popup() -> None:
    result = find_wechat_windows(
        quartz_records_func=lambda: [
            {
                "kCGWindowOwnerName": "WeChat",
                "kCGWindowName": "Edit Contact",
                "kCGWindowNumber": 7,
                "kCGWindowBounds": {"X": 100, "Y": 100, "Width": 408, "Height": 654},
                "kCGWindowIsOnscreen": True,
            },
            {
                "kCGWindowOwnerName": "WeChat",
                "kCGWindowName": "Weixin",
                "kCGWindowNumber": 42,
                "kCGWindowBounds": {"X": 10, "Y": 20, "Width": 900, "Height": 700},
                "kCGWindowIsOnscreen": True,
            },
        ],
        applescript_records_func=lambda app_name: [],
    )

    assert result.ok is True
    assert result.windows[0].window_id == 42
    assert result.windows[0].is_probable_main_window is True


def test_window_model_skips_implausibly_small_windows() -> None:
    window = WeChatWindow(
        window_id=1,
        owner_name="WeChat",
        window_title="Weixin",
        bounds=WindowBounds(0, 0, 120, 80),
        is_visible=True,
        is_minimized_or_hidden=False,
    )

    assert window.can_attempt_background_capture is False


def test_activation_fallback_is_disabled_by_default() -> None:
    config = load_config()

    assert config["background_scan"]["allow_activate_wechat_fallback"] is False
    assert config["background_scan"]["prefer_background_capture"] is True
    assert config["dry_run"] is True
    assert config["allow_real_send"] is False
