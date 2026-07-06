"""macOS WeChat window discovery skeleton for background scanning."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WindowBounds:
    x: int
    y: int
    width: int
    height: int

    @property
    def is_plausible(self) -> bool:
        return self.width > 200 and self.height > 200


@dataclass(frozen=True)
class WeChatWindow:
    window_id: int | None
    owner_name: str
    window_title: str
    bounds: WindowBounds
    is_visible: bool
    is_minimized_or_hidden: bool | None = None

    @property
    def can_attempt_background_capture(self) -> bool:
        return self.is_visible and self.is_minimized_or_hidden is not True and self.bounds.is_plausible


@dataclass(frozen=True)
class WindowLocatorResult:
    ok: bool
    windows: list[WeChatWindow]
    message: str
    error: str | None = None


def _normalize_window_record(record: dict[str, Any]) -> WeChatWindow | None:
    owner = str(record.get("owner_name") or record.get("kCGWindowOwnerName") or "").strip()
    title = str(record.get("window_title") or record.get("kCGWindowName") or "").strip()
    if owner not in {"WeChat", "Weixin"} and "WeChat" not in owner and "微信" not in owner:
        return None

    bounds_raw = record.get("bounds") or record.get("kCGWindowBounds") or {}
    try:
        bounds = WindowBounds(
            x=int(bounds_raw.get("X", bounds_raw.get("x", 0))),
            y=int(bounds_raw.get("Y", bounds_raw.get("y", 0))),
            width=int(bounds_raw.get("Width", bounds_raw.get("width", 0))),
            height=int(bounds_raw.get("Height", bounds_raw.get("height", 0))),
        )
    except Exception:
        LOGGER.debug("Skipping WeChat window with invalid bounds: %r", record)
        return None

    window_id_raw = record.get("window_id", record.get("kCGWindowNumber"))
    try:
        window_id = int(window_id_raw) if window_id_raw is not None else None
    except Exception:
        window_id = None

    is_visible = bool(record.get("is_visible", record.get("kCGWindowIsOnscreen", True)))
    minimized = record.get("is_minimized_or_hidden")
    if minimized is not None:
        minimized = bool(minimized)

    return WeChatWindow(
        window_id=window_id,
        owner_name=owner,
        window_title=title,
        bounds=bounds,
        is_visible=is_visible,
        is_minimized_or_hidden=minimized,
    )


def _quartz_window_records() -> list[dict[str, Any]]:
    try:
        import Quartz  # type: ignore
    except Exception as exc:  # pragma: no cover - optional macOS dependency
        raise RuntimeError(f"Quartz unavailable: {exc}") from exc

    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    records = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    return list(records or [])


def _applescript_window_records(app_name: str = "WeChat") -> list[dict[str, Any]]:
    script = f"""
tell application "System Events"
    if not (exists process "{app_name}") then return ""
    tell process "{app_name}"
        set output to {{}}
        repeat with w in windows
            set {{wx, wy}} to position of w
            set {{ww, wh}} to size of w
            set end of output to (name of w as string) & "|" & wx & "," & wy & "," & ww & "," & wh
        end repeat
        return output as string
    end tell
end tell
"""
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "AppleScript window lookup failed")

    records: list[dict[str, Any]] = []
    raw = result.stdout.strip()
    if not raw:
        return records
    for item in raw.split(", "):
        if "|" not in item:
            continue
        title, bounds_text = item.split("|", 1)
        parts = [part.strip() for part in bounds_text.split(",")]
        if len(parts) != 4:
            continue
        records.append(
            {
                "owner_name": app_name,
                "window_title": title,
                "bounds": {
                    "x": int(float(parts[0])),
                    "y": int(float(parts[1])),
                    "width": int(float(parts[2])),
                    "height": int(float(parts[3])),
                },
                "is_visible": True,
                "is_minimized_or_hidden": None,
            }
        )
    return records


def find_wechat_windows(
    *,
    app_name: str = "WeChat",
    quartz_records_func: Callable[[], list[dict[str, Any]]] = _quartz_window_records,
    applescript_records_func: Callable[[str], list[dict[str, Any]]] = _applescript_window_records,
) -> WindowLocatorResult:
    """Find WeChat windows without activating WeChat.

    Quartz is preferred because it can provide a window id. AppleScript is a
    fallback for geometry only. Both paths inspect macOS window metadata, not
    WeChat data stores.
    """
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    try:
        records = quartz_records_func()
    except Exception as exc:
        errors.append(str(exc))
        LOGGER.info("Quartz WeChat window lookup unavailable: %s", exc)

    if not records:
        try:
            records = applescript_records_func(app_name)
        except Exception as exc:
            errors.append(str(exc))
            LOGGER.warning("AppleScript WeChat window lookup unavailable: %s", exc)

    windows = [window for record in records if (window := _normalize_window_record(record)) is not None]
    capturable = [window for window in windows if window.can_attempt_background_capture]
    if capturable:
        return WindowLocatorResult(True, capturable, f"Found {len(capturable)} visible WeChat window(s).")
    if windows:
        return WindowLocatorResult(False, windows, "WeChat windows found but none are visible/capturable.")
    error = "; ".join(errors) if errors else None
    return WindowLocatorResult(False, [], "No visible WeChat window found.", error=error)
