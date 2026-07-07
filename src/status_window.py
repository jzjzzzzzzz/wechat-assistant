"""OCR-friendly floating owner-status control window.

Safe to import: no GUI loop starts at import time, and this module does not
scan WeChat, OCR WeChat, control WeChat, or send messages.  The runtime command
only reads/writes owner_status in the local project database.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import sys
from typing import Any

from src.owner_status import get_owner_status, set_owner_status


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class StatusWindowOptions:
    width: int = 220
    height: int = 46
    margin_right: int = 24
    margin_top: int = 142
    refresh_seconds: float = 1.0
    locked_on_top: bool = True


def status_window_text_for_status(status: str) -> str:
    return "OL" if status == "online" else "OFF"


def status_window_button_title_for_status(status: str) -> str:
    return status_window_text_for_status(status)


def status_window_lock_button_title(locked: bool) -> str:
    return "UNLOCK" if locked else "LOCK"


def status_window_text_color_for_status(status: str) -> str:
    return "#00b847" if status == "online" else "#e1141c"


def status_window_options(config: dict[str, Any]) -> StatusWindowOptions:
    owner = config.get("owner", {}) if isinstance(config.get("owner"), dict) else {}
    raw = owner.get("status_window", {}) if isinstance(owner.get("status_window"), dict) else {}

    def int_option(key: str, default: int, *, min_value: int, max_value: int) -> int:
        try:
            value = int(raw.get(key, default))
        except (TypeError, ValueError):
            value = default
        return min(max_value, max(min_value, value))

    def float_option(key: str, default: float, *, min_value: float, max_value: float) -> float:
        try:
            value = float(raw.get(key, default))
        except (TypeError, ValueError):
            value = default
        return min(max_value, max(min_value, value))

    return StatusWindowOptions(
        width=int_option("width", 220, min_value=160, max_value=420),
        height=int_option("height", 46, min_value=32, max_value=100),
        margin_right=int_option("margin_right", 24, min_value=0, max_value=1200),
        margin_top=int_option("margin_top", 142, min_value=0, max_value=500),
        refresh_seconds=float_option("refresh_seconds", 1.0, min_value=0.25, max_value=10.0),
        locked_on_top=bool(raw.get("locked_on_top", True)),
    )


def _load_tkinter() -> Any:
    import tkinter as tk

    return tk


def status_window_check(config: dict[str, Any]) -> int:
    print(f"Python executable: {sys.executable}")
    tk_available = False
    tk_version = "unavailable"
    try:
        tk = _load_tkinter()
        tk_available = True
        tk_version = str(getattr(tk, "TkVersion", "unknown"))
    except Exception as exc:
        tk_version = f"unavailable ({exc})"

    owner = get_owner_status(config)
    options = status_window_options(config)
    print(f"Tkinter import: {'ok' if tk_available else 'failed'}")
    print(f"Tk version: {tk_version}")
    print(f"owner status: {owner.status}")
    print(f"status source: {owner.source}")
    print(f"updated_at: {owner.updated_at.isoformat(timespec='seconds') if owner.updated_at else 'none'}")
    print(f"expected status button: {status_window_button_title_for_status(owner.status)}")
    print(
        "window: "
        f"width={options.width} height={options.height} "
        f"margin_right={options.margin_right} margin_top={options.margin_top} "
        f"locked_on_top={options.locked_on_top}"
    )
    print(f"refresh_seconds: {options.refresh_seconds:.2f}")
    print(f"GUI loop would start: {tk_available}")
    return 0 if tk_available else 1


def _apply_transparent_window(root: Any) -> None:
    """Best-effort transparent background for macOS/Tk."""
    root.configure(bg="#010203")
    try:
        root.attributes("-transparent", True)
    except Exception:
        pass
    try:
        root.attributes("-transparentcolor", "#010203")
    except Exception:
        pass
    try:
        root.attributes("-alpha", 0.96)
    except Exception:
        pass


def run_status_window(config: dict[str, Any]) -> int:
    owner = config.get("owner", {}) if isinstance(config.get("owner"), dict) else {}
    if not owner.get("status_window_enabled", True):
        print("status-window is disabled by config owner.status_window_enabled.")
        return 2

    try:
        tk = _load_tkinter()
    except Exception as exc:
        print("status-window requires tkinter. CLI owner-status commands remain available.")
        print(f"Exception: {exc}")
        return 1

    options = status_window_options(config)

    root = tk.Tk()
    root.title("WeChat Assistant Status")
    root.overrideredirect(True)
    root.resizable(False, False)
    _apply_transparent_window(root)

    screen_width = root.winfo_screenwidth()
    x = max(0, screen_width - options.margin_right - options.width)
    y = max(0, options.margin_top)
    root.geometry(f"{options.width}x{options.height}+{x}+{y}")

    locked_on_top = {"value": bool(options.locked_on_top)}
    last_status = {"value": ""}
    last_text = {"value": ""}

    def apply_lock_state() -> None:
        root.attributes("-topmost", bool(locked_on_top["value"]))
        lock_button.configure(text=status_window_lock_button_title(bool(locked_on_top["value"])))
        if locked_on_top["value"]:
            root.lift()

    def refresh() -> None:
        try:
            status = get_owner_status(config).status
            text = status_window_button_title_for_status(status)
            status_button.configure(
                text=text,
                foreground=status_window_text_color_for_status(status),
                activeforeground=status_window_text_color_for_status(status),
            )
            if status != last_status["value"] or text != last_text["value"]:
                LOGGER.info("status-window changed: %s -> %s", last_text["value"] or "none", text)
                last_status["value"] = status
                last_text["value"] = text
            if locked_on_top["value"]:
                root.lift()
        except Exception as exc:
            LOGGER.warning("status-window refresh failed safely: %s", exc)
        root.after(int(options.refresh_seconds * 1000), refresh)

    def toggle_status() -> None:
        try:
            current = get_owner_status(config).status
            next_status = "offline" if current == "online" else "online"
            set_owner_status(
                config,
                next_status,
                updated_by="status-window",
                note="status button toggle",
            )
            LOGGER.info("status-window button toggled owner status: %s -> %s", current, next_status)
            refresh()
        except Exception as exc:
            LOGGER.warning("status-window toggle status failed safely: %s", exc)

    def toggle_lock() -> None:
        locked_on_top["value"] = not locked_on_top["value"]
        LOGGER.info("status-window foreground lock changed: locked_on_top=%s", locked_on_top["value"])
        apply_lock_state()

    status_button = tk.Button(
        root,
        text="OL",
        command=toggle_status,
        font=("Helvetica", 28, "bold"),
        width=4,
        borderwidth=1,
        highlightthickness=0,
        takefocus=False,
    )
    lock_button = tk.Button(
        root,
        text=status_window_lock_button_title(locked_on_top["value"]),
        command=toggle_lock,
        font=("Helvetica", 13, "bold"),
        width=9,
        borderwidth=1,
        highlightthickness=0,
        takefocus=False,
    )
    status_button.pack(side="left", fill="both", expand=True, padx=(0, 8))
    lock_button.pack(side="left", fill="both", expand=True)

    apply_lock_state()
    refresh()
    current = get_owner_status(config)
    print("Starting OCR-friendly status window...")
    print(f"Expected status button: {status_window_button_title_for_status(current.status)}")
    print(f"Refresh interval: {options.refresh_seconds:.2f}s")
    print("Look below the iBar menu bar area.")
    try:
        root.mainloop()
        LOGGER.warning("status-window GUI loop exited unexpectedly.")
        return 0
    except KeyboardInterrupt:
        LOGGER.info("status-window stopped by Ctrl+C.")
        return 0
    except Exception as exc:
        print("Could not start status window.")
        print(f"Exception: {exc}")
        return 1


def run_status_window_test(config: dict[str, Any]) -> int:
    copied = dict(config)
    owner = dict(copied.get("owner", {}) if isinstance(copied.get("owner"), dict) else {})
    owner["status_window"] = {
        **(owner.get("status_window", {}) if isinstance(owner.get("status_window"), dict) else {}),
        "width": 220,
    }
    copied["owner"] = owner
    return run_status_window(copied)
