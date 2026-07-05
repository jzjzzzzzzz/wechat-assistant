"""Task management GUI for local birthday tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.scheduler import BIRTHDAY_TASKS_PATH, build_birthday_plans, load_birthday_tasks, validate_birthday_task


TASK_COLUMNS = ["wechat_remark", "birthday", "message", "enabled"]


@dataclass(frozen=True)
class TaskSaveResult:
    ok: bool
    message: str


class TasksViewModel:
    def __init__(self, config: dict[str, Any], task_path: str | Path = BIRTHDAY_TASKS_PATH) -> None:
        self.config = config
        self.task_path = Path(task_path)
        self.task_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.task_path.exists():
            pd.DataFrame(columns=TASK_COLUMNS).to_csv(self.task_path, index=False, encoding="utf-8")

    def list_tasks(self) -> list[dict[str, Any]]:
        return load_birthday_tasks(self.task_path)

    def _write_tasks(self, tasks: list[dict[str, Any]]) -> None:
        pd.DataFrame(tasks, columns=TASK_COLUMNS).to_csv(self.task_path, index=False, encoding="utf-8")

    def create_task(self, wechat_remark: str, birthday: str, message: str, enabled: bool = True) -> TaskSaveResult:
        task = {
            "wechat_remark": wechat_remark.strip(),
            "birthday": birthday.strip(),
            "message": message.strip(),
            "enabled": "true" if enabled else "false",
        }
        errors = validate_birthday_task(task)
        if errors:
            return TaskSaveResult(False, "; ".join(errors))

        tasks = self.list_tasks()
        tasks.append(task)
        self._write_tasks(tasks)
        return TaskSaveResult(True, "Task created")

    def disable_task(self, index: int) -> TaskSaveResult:
        tasks = self.list_tasks()
        if index < 0 or index >= len(tasks):
            return TaskSaveResult(False, "Task index out of range")
        tasks[index]["enabled"] = "false"
        self._write_tasks(tasks)
        return TaskSaveResult(True, "Task disabled")

    def preview_today(self, today: date | None = None) -> list[dict[str, Any]]:
        run_date = today or date.today()
        return [plan.as_dict() for plan in build_birthday_plans(self.list_tasks(), self.config, run_date)]


def run_tasks_window(config: dict[str, Any]) -> None:
    import tkinter as tk
    from tkinter import ttk

    view_model = TasksViewModel(config)
    window = tk.Toplevel()
    window.title("Tasks")
    window.geometry("820x460")
    window.minsize(720, 400)

    frame = ttk.Frame(window, padding=12)
    frame.pack(fill="both", expand=True)

    columns = ("wechat_remark", "birthday", "message", "enabled")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
    for column in columns:
        tree.heading(column, text=column)
        tree.column(column, width=160, stretch=True)
    tree.pack(fill="both", expand=True)

    form = ttk.Frame(frame)
    form.pack(fill="x", pady=(8, 4))
    remark_var = tk.StringVar(value="文件传输助手")
    birthday_var = tk.StringVar(value="01-01")
    message_var = tk.StringVar(value="生日快乐")
    enabled_var = tk.BooleanVar(value=True)

    for idx, (label, var) in enumerate(
        [("remark", remark_var), ("birthday", birthday_var), ("message", message_var)]
    ):
        ttk.Label(form, text=label).grid(row=0, column=idx * 2, sticky="w")
        ttk.Entry(form, textvariable=var, width=24).grid(row=0, column=idx * 2 + 1, padx=(4, 8))
    ttk.Checkbutton(form, text="enabled", variable=enabled_var).grid(row=0, column=6)

    status = tk.StringVar(value="Tasks are previewed as dry-run plans. No send action is available here.")
    ttk.Label(frame, textvariable=status, wraplength=760).pack(anchor="w", pady=(4, 8))

    def refresh() -> None:
        for item in tree.get_children():
            tree.delete(item)
        for task in view_model.list_tasks():
            tree.insert(
                "",
                "end",
                values=(task["wechat_remark"], task["birthday"], task["message"], task["enabled"]),
            )
        status.set("Tasks refreshed.")

    def create() -> None:
        result = view_model.create_task(
            remark_var.get(),
            birthday_var.get(),
            message_var.get(),
            enabled=enabled_var.get(),
        )
        status.set(result.message)
        if result.ok:
            refresh()

    def disable_selected() -> None:
        selection = tree.selection()
        if not selection:
            status.set("Select a task first.")
            return
        index = tree.index(selection[0])
        result = view_model.disable_task(index)
        status.set(result.message)
        if result.ok:
            refresh()

    def preview() -> None:
        plans = view_model.preview_today()
        status.set(f"Dry-run preview matched {len(plans)} task(s).")

    buttons = ttk.Frame(frame)
    buttons.pack(anchor="w")
    ttk.Button(buttons, text="Refresh", command=refresh).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Create", command=create).grid(row=0, column=1, padx=(0, 8))
    ttk.Button(buttons, text="Disable", command=disable_selected).grid(row=0, column=2, padx=(0, 8))
    ttk.Button(buttons, text="Preview Today", command=preview).grid(row=0, column=3)

    refresh()
