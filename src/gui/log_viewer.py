"""Read-only log viewer helpers and Tkinter window."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_log_path(config: dict[str, Any]) -> Path:
    log_path = Path(str(config.get("log_file", "logs/app.log")))
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path
    return log_path


def tail_log_lines(path: str | Path, max_lines: int = 200, level: str | None = None) -> list[str]:
    log_path = Path(path)
    if not log_path.exists():
        return []

    selected = deque(maxlen=max(1, max_lines))
    level_text = level.upper() if level else None
    with log_path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            line = line.rstrip("\n")
            if level_text and f" {level_text} " not in line:
                continue
            selected.append(line)
    return list(selected)


def run_log_viewer_window(config: dict[str, Any]) -> None:
    import tkinter as tk
    from tkinter import ttk

    log_path = resolve_log_path(config)
    window = tk.Toplevel()
    window.title("Logs")
    window.geometry("860x520")
    window.minsize(720, 420)

    frame = ttk.Frame(window, padding=12)
    frame.pack(fill="both", expand=True)

    controls = ttk.Frame(frame)
    controls.pack(fill="x", pady=(0, 8))

    level_var = tk.StringVar(value="ALL")
    ttk.Label(controls, text=str(log_path)).pack(side="left")
    ttk.Combobox(controls, textvariable=level_var, values=["ALL", "INFO", "WARNING", "ERROR"], width=10).pack(
        side="right"
    )

    text = tk.Text(frame, wrap="word", height=24)
    text.pack(fill="both", expand=True)
    text.configure(state="disabled")

    status = tk.StringVar(value="Read-only log viewer.")
    ttk.Label(frame, textvariable=status).pack(anchor="w", pady=(8, 0))

    def refresh() -> None:
        level = None if level_var.get() == "ALL" else level_var.get()
        lines = tail_log_lines(log_path, max_lines=300, level=level)
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", "\n".join(lines) if lines else "No log lines found.")
        text.configure(state="disabled")
        status.set(f"Loaded {len(lines)} log line(s).")

    ttk.Button(controls, text="Refresh", command=refresh).pack(side="right", padx=(0, 8))
    refresh()
