"""macOS menu bar owner-status switch.

Importing this module must not start a GUI loop. The menu app only reads and
writes the owner status in the project database; it does not scan WeChat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.owner_status import get_owner_status, set_owner_status, toggle_owner_status


def menu_title_for_status(status: str) -> str:
    return "🟢 WeChat Assistant" if status == "online" else "🔴 WeChat Assistant"


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
        import rumps  # type: ignore
    except Exception as exc:
        print("status-menu requires rumps. CLI owner-status commands remain available.")
        print(f"rumps import error: {exc}")
        return 1

    actions = StatusMenuActions(config)

    class WeChatAssistantStatusMenu(rumps.App):  # type: ignore[misc]
        def __init__(self) -> None:
            current = get_owner_status(config)
            super().__init__(menu_title_for_status(current.status))
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

    WeChatAssistantStatusMenu().run()
    return 0
