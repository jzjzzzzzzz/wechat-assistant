from datetime import datetime
from types import SimpleNamespace

import src.status_menu as status_menu
from src.owner_status import OwnerStatusRecord


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


def test_importing_status_menu_does_not_start_gui_loop():
    assert hasattr(status_menu, "run_status_menu")


def test_online_title_is_visible_short_text():
    assert status_menu.menu_title_for_status("online") == "🟢 OL"


def test_offline_title_is_visible_short_text():
    assert status_menu.menu_title_for_status("offline") == "🔴 OFF"


def test_menu_actions_call_owner_status_service_functions(monkeypatch):
    calls = []
    config = {"database_path": "unused.sqlite3"}

    def fake_get_owner_status(cfg):
        calls.append(("get", cfg))
        return OwnerStatusRecord("online", BASE_TIME, "test", None, "database")

    def fake_set_owner_status(cfg, status, *, updated_by="cli", note=None):
        calls.append(("set", status, updated_by))
        return OwnerStatusRecord(status, BASE_TIME, updated_by, note, "database")

    def fake_toggle_owner_status(cfg, *, updated_by="cli"):
        calls.append(("toggle", updated_by))
        return OwnerStatusRecord("offline", BASE_TIME, updated_by, "toggle", "database")

    monkeypatch.setattr(status_menu, "get_owner_status", fake_get_owner_status)
    monkeypatch.setattr(status_menu, "set_owner_status", fake_set_owner_status)
    monkeypatch.setattr(status_menu, "toggle_owner_status", fake_toggle_owner_status)

    actions = status_menu.StatusMenuActions(config)

    assert "status=online" in actions.current_status_text()
    assert actions.set_online() == "online"
    assert actions.set_offline() == "offline"
    assert actions.toggle() == "offline"
    assert ("set", "online", "status-menu") in calls
    assert ("set", "offline", "status-menu") in calls
    assert ("toggle", "status-menu") in calls


def test_menu_actions_do_not_scan_wechat_or_send_messages(monkeypatch):
    calls = []
    config = {"database_path": "unused.sqlite3"}

    monkeypatch.setattr("src.unread_scanner.scan_unread_events", lambda *args, **kwargs: calls.append("scan"))
    monkeypatch.setattr("src.message_sender.send_message", lambda *args, **kwargs: calls.append("send"))
    monkeypatch.setattr(
        status_menu,
        "get_owner_status",
        lambda cfg: OwnerStatusRecord("online", BASE_TIME, "test", None, "database"),
    )
    monkeypatch.setattr(
        status_menu,
        "set_owner_status",
        lambda cfg, value, **kwargs: OwnerStatusRecord(value, BASE_TIME, "test", None, "database"),
    )
    monkeypatch.setattr(
        status_menu,
        "toggle_owner_status",
        lambda cfg, **kwargs: OwnerStatusRecord("offline", BASE_TIME, "test", None, "database"),
    )

    actions = status_menu.StatusMenuActions(config)
    actions.current_status_text()
    actions.set_online()
    actions.set_offline()
    actions.toggle()

    assert calls == []


def test_status_menu_check_exits_without_gui_loop(monkeypatch, tmp_path, capsys):
    class FakeApp:
        def __init__(self, *args, **kwargs):
            raise AssertionError("GUI loop should not be constructed during --check")

    fake_rumps = SimpleNamespace(__version__="1.0-test", App=FakeApp)
    monkeypatch.setattr(status_menu, "_load_rumps", lambda: fake_rumps)
    config = {
        "database_path": str(tmp_path / "wechat_assistant.sqlite3"),
        "owner": {"status_default": "online"},
    }

    result = status_menu.status_menu_check(config)

    output = capsys.readouterr().out
    assert result == 0
    assert "rumps import: ok" in output
    assert "rumps version: 1.0-test" in output
    assert "expected menu title: 🟢 OL" in output
    assert "GUI loop would start: True" in output


def test_status_menu_test_starts_minimal_fake_app(monkeypatch):
    calls = []

    class FakeApp:
        def __init__(self, name, *, title=None, quit_button=None):
            calls.append(("init", name, title, quit_button))
            self.title = title

        def run(self):
            calls.append(("run", self.title))

    fake_rumps = SimpleNamespace(App=FakeApp)
    monkeypatch.setattr(status_menu, "_load_rumps", lambda: fake_rumps)

    result = status_menu.run_status_menu_test()

    assert result == 0
    assert calls == [("init", "WA Test", "🟢 TEST WA", "Quit"), ("run", "🟢 TEST WA")]


def test_status_menu_fallback_does_not_scan_wechat(monkeypatch, capsys):
    result = status_menu.run_status_menu({"owner": {"status_menu_enabled": False}})

    assert result == 2
    output = capsys.readouterr().out
    assert "disabled" in output
