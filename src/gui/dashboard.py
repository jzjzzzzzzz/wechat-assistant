"""Tkinter dashboard for WeChat Assistant."""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.mac_permissions import run_environment_checks
from src.message_sender import send_test_message
from src.screenshot import capture_screenshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DashboardStatus:
    dry_run: bool
    allow_real_send: bool
    test_contact: str
    log_file: str

    @property
    def safety_summary(self) -> str:
        if self.dry_run:
            return "DRY RUN ON - no real messages will be sent"
        if not self.allow_real_send:
            return "REAL SEND BLOCKED - allow_real_send is false"
        return "REAL SEND FLAGS ENABLED - restricted safety gates still apply"


def dashboard_status_from_config(config: dict[str, Any]) -> DashboardStatus:
    return DashboardStatus(
        dry_run=bool(config.get("dry_run", True)),
        allow_real_send=bool(config.get("allow_real_send", False)),
        test_contact=str(config.get("test_contact", "文件传输助手")),
        log_file=str(config.get("log_file", "logs/app.log")),
    )


class DashboardCommandRunner:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        check_func: Callable[[], list[Any]] = run_environment_checks,
        screenshot_func: Callable[[dict[str, Any]], str | None] = capture_screenshot,
        test_send_func: Callable[[dict[str, Any]], bool] = send_test_message,
        open_func: Callable[[list[str]], Any] | None = None,
    ) -> None:
        self.config = config
        self.check_func = check_func
        self.screenshot_func = screenshot_func
        self.test_send_func = test_send_func
        self.open_func = open_func or (lambda args: subprocess.run(args, check=False))

    def run_check(self) -> str:
        results = self.check_func()
        ok = all(getattr(result, "ok", False) for result in results)
        return "Environment check passed" if ok else "Environment check found issues; see logs/app.log"

    def run_screenshot(self) -> str:
        path = self.screenshot_func(self.config)
        return f"Screenshot saved: {path}" if path else "Screenshot failed; see logs/app.log"

    def run_test_send(self) -> str:
        ok = self.test_send_func(self.config)
        mode = "dry-run" if self.config.get("dry_run", True) else "send attempt"
        return f"Test send {mode} completed" if ok else f"Test send {mode} failed or was blocked"

    def open_logs(self) -> str:
        log_path = Path(str(self.config.get("log_file", "logs/app.log")))
        if not log_path.is_absolute():
            log_path = PROJECT_ROOT / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=True)
        self.open_func(["open", str(log_path)])
        return f"Opened log file: {log_path}"


def run_dashboard(config: dict[str, Any]) -> None:
    import tkinter as tk
    from tkinter import ttk

    status = dashboard_status_from_config(config)
    runner = DashboardCommandRunner(config)

    root = tk.Tk()
    root.title("WeChat Assistant")
    root.geometry("560x360")
    root.minsize(520, 320)

    container = ttk.Frame(root, padding=16)
    container.pack(fill="both", expand=True)

    title = ttk.Label(container, text="WeChat Assistant", font=("TkDefaultFont", 18, "bold"))
    title.pack(anchor="w")

    safety = ttk.Label(container, text=status.safety_summary, foreground="red" if not status.dry_run else "green")
    safety.pack(anchor="w", pady=(8, 4))

    details = ttk.Label(
        container,
        text=(
            f"Target: {status.test_contact}\n"
            f"dry_run: {status.dry_run}\n"
            f"allow_real_send: {status.allow_real_send}\n"
            f"Log: {status.log_file}"
        ),
        justify="left",
    )
    details.pack(anchor="w", pady=(0, 12))

    output = tk.StringVar(value="Ready")
    output_label = ttk.Label(container, textvariable=output, wraplength=500, justify="left")
    output_label.pack(anchor="w", fill="x", pady=(12, 0))

    buttons = ttk.Frame(container)
    buttons.pack(anchor="w", fill="x")

    def run_async(action: Callable[[], str]) -> None:
        output.set("Running...")

        def worker() -> None:
            try:
                message = action()
            except Exception as exc:  # pragma: no cover - GUI defensive path
                message = f"Action failed: {exc}"
            root.after(0, lambda: output.set(message))

        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(buttons, text="Check", command=lambda: run_async(runner.run_check)).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Screenshot", command=lambda: run_async(runner.run_screenshot)).grid(
        row=0, column=1, padx=(0, 8)
    )
    ttk.Button(buttons, text="Dry-run Test Send", command=lambda: run_async(runner.run_test_send)).grid(
        row=0, column=2, padx=(0, 8)
    )
    ttk.Button(buttons, text="Logs", command=lambda: run_async(runner.open_logs)).grid(row=0, column=3)

    def open_settings() -> str:
        from src.gui.settings import run_settings_window

        root.after(0, run_settings_window)
        return "Settings opened"

    ttk.Button(buttons, text="Settings", command=lambda: run_async(open_settings)).grid(
        row=0, column=4, padx=(8, 0)
    )

    def open_contacts() -> str:
        from src.gui.contacts import run_contacts_window

        root.after(0, lambda: run_contacts_window(config))
        return "Contacts opened"

    ttk.Button(buttons, text="Contacts", command=lambda: run_async(open_contacts)).grid(
        row=1, column=0, pady=(8, 0)
    )

    def open_tasks() -> str:
        from src.gui.tasks import run_tasks_window

        root.after(0, lambda: run_tasks_window(config))
        return "Tasks opened"

    ttk.Button(buttons, text="Tasks", command=lambda: run_async(open_tasks)).grid(
        row=1, column=1, padx=(8, 0), pady=(8, 0)
    )

    root.mainloop()
