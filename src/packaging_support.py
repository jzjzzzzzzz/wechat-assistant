"""Packaging helpers for macOS builds."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_EXCLUDE_DIRS = {".venv", ".pytest_cache", "__pycache__", "logs", "screenshots", "debug", "dist", "build"}
PRIVATE_EXCLUDE_SUFFIXES = {".sqlite3", ".sqlite3-wal", ".sqlite3-shm", ".log", ".png", ".jpg", ".jpeg"}


def should_exclude_from_package(path: str | Path) -> bool:
    item = Path(path)
    parts = set(item.parts)
    if parts & PRIVATE_EXCLUDE_DIRS:
        return True
    return any(str(item).endswith(suffix) for suffix in PRIVATE_EXCLUDE_SUFFIXES)


def pyinstaller_command() -> list[str]:
    return [
        "pyinstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        "WeChat Assistant",
        "--add-data",
        "config/settings.yaml:config",
        "--add-data",
        "data/birthday_tasks.csv:data",
        "--add-data",
        "data/message_templates.csv:data",
        "--add-data",
        "data/festival_tasks.csv:data",
        "--add-data",
        "data/reminders.csv:data",
        "packaging/pyinstaller_entry.py",
    ]
