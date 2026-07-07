"""Manage the auto-reply private chat whitelist in settings.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from src.auto_reply_policy import normalize_chat_sender
from src.config_loader import DEFAULT_CONFIG_PATH


WhitelistAction = Literal["added", "already_present", "removed", "not_found"]


@dataclass(frozen=True)
class WhitelistUpdateResult:
    action: WhitelistAction
    sender: str
    path: Path
    entries: list[str]


def _load_raw_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    if not isinstance(raw, dict):
        raise ValueError("settings.yaml must contain a YAML mapping")
    return raw


def _config_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else DEFAULT_CONFIG_PATH


def read_private_whitelist(path: str | Path | None = None) -> list[str]:
    config_path = _config_path(path)
    raw = _load_raw_config(config_path)
    auto_reply = raw.get("auto_reply", {})
    if not isinstance(auto_reply, dict):
        return []
    values = auto_reply.get("private_chat_whitelist", [])
    if not isinstance(values, list):
        return []
    return [
        normalize_chat_sender(str(item))
        for item in values
        if normalize_chat_sender(str(item))
    ]


def _quote_yaml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _find_whitelist_block(lines: list[str]) -> tuple[int, int, str, str]:
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped != "private_chat_whitelist:":
            continue
        key_indent = line[: len(line) - len(line.lstrip(" "))]
        item_indent = key_indent + "  "
        end = index + 1
        while end < len(lines):
            next_line = lines[end]
            if not next_line.strip():
                end += 1
                continue
            indent = next_line[: len(next_line) - len(next_line.lstrip(" "))]
            if len(indent) <= len(key_indent) and not next_line.lstrip().startswith("- "):
                break
            if len(indent) == len(key_indent) and next_line.strip().endswith(":"):
                break
            end += 1
        return index, end, key_indent, item_indent
    raise ValueError("auto_reply.private_chat_whitelist block not found in settings.yaml")


def _write_whitelist(path: Path, entries: list[str]) -> None:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    start, end, key_indent, item_indent = _find_whitelist_block(lines)
    block = [lines[start]]
    if entries:
        block.extend(f"{item_indent}- {_quote_yaml_string(entry)}" for entry in entries)
    else:
        block = [f"{key_indent}private_chat_whitelist: []"]
    updated_lines = lines[:start] + block + lines[end:]
    trailing_newline = "\n" if original.endswith("\n") else ""
    path.write_text("\n".join(updated_lines) + trailing_newline, encoding="utf-8")


def add_private_whitelist_sender(
    sender: str,
    *,
    path: str | Path | None = None,
) -> WhitelistUpdateResult:
    config_path = _config_path(path)
    normalized = normalize_chat_sender(sender)
    if not normalized:
        raise ValueError("sender must not be empty")
    entries = read_private_whitelist(config_path)
    if any(entry.casefold() == normalized.casefold() for entry in entries):
        return WhitelistUpdateResult("already_present", normalized, config_path, entries)
    entries.append(normalized)
    _write_whitelist(config_path, entries)
    return WhitelistUpdateResult("added", normalized, config_path, entries)


def remove_private_whitelist_sender(
    sender: str,
    *,
    path: str | Path | None = None,
) -> WhitelistUpdateResult:
    config_path = _config_path(path)
    normalized = normalize_chat_sender(sender)
    if not normalized:
        raise ValueError("sender must not be empty")
    entries = read_private_whitelist(config_path)
    filtered = [entry for entry in entries if entry.casefold() != normalized.casefold()]
    if len(filtered) == len(entries):
        return WhitelistUpdateResult("not_found", normalized, config_path, entries)
    _write_whitelist(config_path, filtered)
    return WhitelistUpdateResult("removed", normalized, config_path, filtered)
