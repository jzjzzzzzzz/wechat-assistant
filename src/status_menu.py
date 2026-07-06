"""macOS menu bar owner-status switch.

Importing this module must not start a GUI loop. The menu app only reads and
writes the owner status in the project database; it does not scan WeChat.
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Any

from src.owner_status import get_owner_status, set_owner_status, toggle_owner_status


def menu_title_for_status(status: str) -> str:
    return "🟢 WA ONLINE" if status == "online" else "🔴 WA OFFLINE"


def print_cli_fallback() -> None:
    print("CLI alternatives:")
    print("  python -m src.main owner-status")
    print("  python -m src.main owner-status set online")
    print("  python -m src.main owner-status set offline")


def _load_rumps() -> Any:
    import rumps  # type: ignore

    return rumps


def status_menu_check(config: dict[str, Any]) -> int:
    print(f"Python executable: {sys.executable}")
    rumps_available = False
    rumps_version = "unavailable"
    try:
        rumps = _load_rumps()
        rumps_available = True
        rumps_version = str(getattr(rumps, "__version__", "unknown"))
    except Exception as exc:
        rumps_version = f"unavailable ({exc})"
    status = get_owner_status(config)
    print(f"rumps import: {'ok' if rumps_available else 'failed'}")
    print(f"rumps version: {rumps_version}")
    print(f"owner status: {status.status}")
    print(f"status source: {status.source}")
    print(f"updated_at: {status.updated_at.isoformat(timespec='seconds') if status.updated_at else 'none'}")
    print(f"expected menu title: {menu_title_for_status(status.status)}")
    print(f"GUI loop would start: {rumps_available}")
    return 0 if rumps_available else 1


@dataclass
class StatusMenuActions:
    config: dict[str, Any]

    def current_status_text(self) -> str:
        status = get_owner_status(self.config)
        updated = status.updated_at.isoformat(timespec="seconds") if status.updated_at else "none"
        return f"status={status.status} source={status.source} updated_at={updated}"

    def set_online(self) -> str:
        status = set_owner_status(self.config, "online", updated_by="status-menu")
        return status.status

    def set_offline(self) -> str:
        status = set_owner_status(self.config, "offline", updated_by="status-menu")
        return status.status

    def toggle(self) -> str:
        status = toggle_owner_status(self.config, updated_by="status-menu")
        return status.status


def run_status_menu(config: dict[str, Any]) -> int:
    owner = config.get("owner", {}) if isinstance(config.get("owner"), dict) else {}
    if not owner.get("status_menu_enabled", True):
        print("status-menu is disabled by config owner.status_menu_enabled.")
        return 2

    try:
        rumps = _load_rumps()
    except Exception as exc:
        print("status-menu requires rumps. CLI owner-status commands remain available.")
        print(f"Exception: {exc}")
        print_cli_fallback()
        return 1

    actions = StatusMenuActions(config)

    class WeChatAssistantStatusMenu(rumps.App):  # type: ignore[misc]
        def __init__(self) -> None:
            current = get_owner_status(config)
            expected_title = menu_title_for_status(current.status)
            super().__init__("WeChat Assistant", title=expected_title, quit_button=None)
            self.title = expected_title
            self.menu = [
                rumps.MenuItem("Set Online", callback=self.set_online),
                rumps.MenuItem("Set Offline", callback=self.set_offline),
                rumps.MenuItem("Toggle Status", callback=self.toggle_status),
                rumps.MenuItem("Show Current Status", callback=self.show_current_status),
                None,
                rumps.MenuItem("Quit", callback=rumps.quit_application),
            ]

        def refresh_title(self) -> None:
            self.title = menu_title_for_status(get_owner_status(config).status)

        def set_online(self, _sender: Any) -> None:
            actions.set_online()
            self.refresh_title()

        def set_offline(self, _sender: Any) -> None:
            actions.set_offline()
            self.refresh_title()

        def toggle_status(self, _sender: Any) -> None:
            actions.toggle()
            self.refresh_title()

        def show_current_status(self, _sender: Any) -> None:
            rumps.notification("WeChat Assistant", "Owner Status", actions.current_status_text())
            self.refresh_title()

    try:
        current = get_owner_status(config)
        expected_title = menu_title_for_status(current.status)
        print("Starting macOS menu bar app...")
        print(f"Expected menu title: {expected_title}")
        print("Look near Wi-Fi / battery / clock in the top-right menu bar.")
        app = WeChatAssistantStatusMenu()
        app.run()
        return 0
    except Exception as exc:
        print("Could not start macOS menu bar app.")
        print(f"Exception: {exc}")
        print_cli_fallback()
        return 1


def run_status_menu_test() -> int:
    try:
        rumps = _load_rumps()
    except Exception as exc:
        print("status-menu --test requires rumps.")
        print(f"Exception: {exc}")
        print_cli_fallback()
        return 1

    class TestStatusMenu(rumps.App):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__("WA Test", title="🟢 TEST WA", quit_button="Quit")
            self.title = "🟢 TEST WA"

    try:
        print("Starting minimal macOS menu bar test app...")
        print("Expected menu title: 🟢 TEST WA")
        print("Look near Wi-Fi / battery / clock in the top-right menu bar.")
        TestStatusMenu().run()
        return 0
    except Exception as exc:
        print("Could not start minimal macOS menu bar test app.")
        print(f"Exception: {exc}")
        print_cli_fallback()
        return 1
