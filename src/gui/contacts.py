"""Contacts review GUI for local project-owned contacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.contact_manager import disable_contact, list_all_local_contacts, mark_contact_reviewed
from src.database import connect_database, initialize_database


@dataclass(frozen=True)
class ContactRow:
    contact_name: str
    source: str
    confidence: float
    reviewed: bool
    enabled: bool


class ContactsViewModel:
    exposed_actions = ("refresh", "mark_reviewed", "disable")

    def __init__(self, config: dict[str, Any]) -> None:
        self.database_path = str(config.get("database_path", "data/wechat_assistant.sqlite3"))
        initialize_database(self.database_path)

    def list_contacts(self) -> list[ContactRow]:
        with connect_database(self.database_path) as connection:
            rows = list_all_local_contacts(connection)
        return [
            ContactRow(
                contact_name=str(row["contact_name"]),
                source=str(row["source"]),
                confidence=float(row["confidence"]),
                reviewed=bool(row["reviewed"]),
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]

    def mark_reviewed(self, contact_name: str) -> bool:
        with connect_database(self.database_path) as connection:
            return mark_contact_reviewed(connection, contact_name, reviewed=True)

    def disable(self, contact_name: str) -> bool:
        with connect_database(self.database_path) as connection:
            return disable_contact(connection, contact_name)


def run_contacts_window(config: dict[str, Any]) -> None:
    import tkinter as tk
    from tkinter import ttk

    view_model = ContactsViewModel(config)
    window = tk.Toplevel()
    window.title("Contacts")
    window.geometry("760x420")
    window.minsize(680, 360)

    frame = ttk.Frame(window, padding=12)
    frame.pack(fill="both", expand=True)

    columns = ("contact_name", "source", "confidence", "reviewed", "enabled")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)
    for column in columns:
        tree.heading(column, text=column)
        tree.column(column, width=140, stretch=True)
    tree.pack(fill="both", expand=True)

    status = tk.StringVar(value="Contacts are local project records. No send action is available here.")
    ttk.Label(frame, textvariable=status, wraplength=720).pack(anchor="w", pady=(8, 8))

    def selected_name() -> str | None:
        selection = tree.selection()
        if not selection:
            status.set("Select a contact first.")
            return None
        values = tree.item(selection[0], "values")
        return str(values[0]) if values else None

    def refresh() -> None:
        for item in tree.get_children():
            tree.delete(item)
        for row in view_model.list_contacts():
            tree.insert(
                "",
                "end",
                values=(row.contact_name, row.source, f"{row.confidence:.2f}", row.reviewed, row.enabled),
            )
        status.set("Contacts refreshed.")

    def mark_selected_reviewed() -> None:
        name = selected_name()
        if name and view_model.mark_reviewed(name):
            status.set(f"Marked reviewed: {name}")
            refresh()

    def disable_selected() -> None:
        name = selected_name()
        if name and view_model.disable(name):
            status.set(f"Disabled contact: {name}")
            refresh()

    buttons = ttk.Frame(frame)
    buttons.pack(anchor="w")
    ttk.Button(buttons, text="Refresh", command=refresh).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Mark Reviewed", command=mark_selected_reviewed).grid(row=0, column=1, padx=(0, 8))
    ttk.Button(buttons, text="Disable", command=disable_selected).grid(row=0, column=2)

    refresh()
