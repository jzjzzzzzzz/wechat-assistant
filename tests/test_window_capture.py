from src.window_capture import capture_visible_region, capture_wechat_window
from src.window_locator import WeChatWindow, WindowBounds


def make_config(tmp_path):
    return {
        "background_scan": {
            "debug_screenshot_dir": str(tmp_path),
        }
    }


def test_capture_wechat_window_returns_structured_failure_for_hidden_window(tmp_path):
    window = WeChatWindow(
        window_id=42,
        owner_name="WeChat",
        window_title="Weixin",
        bounds=WindowBounds(10, 20, 900, 700),
        is_visible=False,
        is_minimized_or_hidden=True,
    )

    result = capture_wechat_window(window, make_config(tmp_path))

    assert result.success is False
    assert result.capture_method == "none"
    assert result.image_path is None
    assert result.bounds == (10, 20, 900, 700)


def test_capture_visible_region_returns_structured_failure_when_screenshot_fails(tmp_path):
    window = WeChatWindow(
        window_id=42,
        owner_name="WeChat",
        window_title="Weixin",
        bounds=WindowBounds(10, 20, 900, 700),
        is_visible=True,
        is_minimized_or_hidden=False,
    )

    result = capture_visible_region(
        window,
        make_config(tmp_path),
        screenshot_func=lambda: (_ for _ in ()).throw(RuntimeError("screen recording denied")),
        size_func=lambda: (1440, 900),
    )

    assert result.success is False
    assert result.capture_method == "visible_region"
    assert result.error == "screen recording denied"
    assert "Screen Recording permission" in result.message
