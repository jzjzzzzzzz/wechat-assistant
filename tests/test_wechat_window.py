import sys
from types import SimpleNamespace

from src import wechat_window
from src.wechat_window import UiActionResult


class Completed:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_activate_wechat_success(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args, check=False, capture_output=True, text=True):
        calls.append(args)
        if args[0] == "osascript" and "System Events" in args[-1]:
            return Completed(stdout="true\n")
        return Completed(returncode=0)

    monkeypatch.setattr(wechat_window.subprocess, "run", fake_run)
    monkeypatch.setattr(wechat_window.time, "sleep", lambda seconds: None)

    result = wechat_window.activate_wechat_result("WeChat", wait_seconds=0, retry_count=1)

    assert result.ok is True
    assert result.action == "activate_wechat"
    assert any(args[0] == "osascript" for args in calls)


def test_activate_wechat_failure(monkeypatch) -> None:
    def fake_run(args, check=False, capture_output=True, text=True):
        if args[0] == "osascript" and "System Events" in args[-1]:
            return Completed(stdout="true\n")
        return Completed(returncode=1, stderr="not allowed")

    monkeypatch.setattr(wechat_window.subprocess, "run", fake_run)
    monkeypatch.setattr(wechat_window.time, "sleep", lambda seconds: None)

    result = wechat_window.activate_wechat_result("WeChat", wait_seconds=0, retry_count=2)

    assert result.ok is False
    assert result.attempt == 2
    assert "Failed to activate WeChat" in result.message


def test_search_contact_success_uses_keyboard_and_clipboard(monkeypatch) -> None:
    actions: list[tuple[str, tuple[str, ...] | str]] = []

    class FakePyAutoGui:
        @staticmethod
        def hotkey(*keys):
            actions.append(("hotkey", keys))

        @staticmethod
        def press(key):
            actions.append(("press", key))

    fake_pyperclip = SimpleNamespace(copy=lambda text: actions.append(("copy", text)))

    monkeypatch.setattr(
        wechat_window,
        "activate_wechat_result",
        lambda app_name, wait_seconds, retry_count: UiActionResult("activate_wechat", True, "ok"),
    )
    monkeypatch.setattr(wechat_window, "_import_pyautogui", lambda: (FakePyAutoGui, None))
    monkeypatch.setitem(sys.modules, "pyperclip", fake_pyperclip)
    monkeypatch.setattr(wechat_window.time, "sleep", lambda seconds: None)

    result = wechat_window.search_contact_result(
        "文件传输助手",
        {
            "wechat_app_name": "WeChat",
            "search_delay_seconds": 0,
            "ui_action_interval_seconds": 0,
            "max_retry": 1,
        },
    )

    assert result.ok is True
    assert actions == [
        ("hotkey", ("command", "f")),
        ("hotkey", ("command", "a")),
        ("copy", "文件传输助手"),
        ("hotkey", ("command", "v")),
        ("press", "enter"),
    ]


def test_search_contact_failure_captures_screenshot(monkeypatch) -> None:
    screenshots: list[str] = []

    class FailingPyAutoGui:
        @staticmethod
        def hotkey(*keys):
            raise RuntimeError("keyboard blocked")

    monkeypatch.setattr(
        wechat_window,
        "activate_wechat_result",
        lambda app_name, wait_seconds, retry_count: UiActionResult("activate_wechat", True, "ok"),
    )
    monkeypatch.setattr(wechat_window, "_import_pyautogui", lambda: (FailingPyAutoGui, None))
    monkeypatch.setitem(sys.modules, "pyperclip", SimpleNamespace(copy=lambda text: None))
    monkeypatch.setattr(wechat_window.time, "sleep", lambda seconds: None)

    result = wechat_window.search_contact_result(
        "文件传输助手",
        {
            "wechat_app_name": "WeChat",
            "search_delay_seconds": 0,
            "ui_action_interval_seconds": 0,
            "max_retry": 2,
        },
        screenshot_func=lambda config: screenshots.append("failure.png") or "failure.png",
    )

    assert result.ok is False
    assert result.attempt == 2
    assert result.screenshot_path == "failure.png"
    assert screenshots == ["failure.png", "failure.png"]
