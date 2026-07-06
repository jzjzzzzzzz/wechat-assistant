from datetime import datetime

import src.status_menu as status_menu
from src.owner_status import OwnerStatusRecord


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


def test_importing_status_menu_does_not_start_gui_loop():
    assert hasattr(status_menu, "run_status_menu")


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


def test_status_menu_fallback_does_not_scan_wechat(monkeypatch, capsys):
    monkeypatch.setattr(status_menu, "__import__", None, raising=False)
    result = status_menu.run_status_menu({"owner": {"status_menu_enabled": False}})

    assert result == 2
    output = capsys.readouterr().out
    assert "disabled" in output
