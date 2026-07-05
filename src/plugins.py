"""Safe local plugin manifest loader.

This skeleton validates local plugin manifests only. It intentionally does not
execute plugin code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = PROJECT_ROOT / "plugins"
ALLOWED_CAPABILITIES = {"template_provider", "reminder_rule"}
FORBIDDEN_CAPABILITIES = {"direct_send", "pyautogui_access", "credential_access", "wechat_database_access"}


class PluginError(ValueError):
    """Raised when a plugin manifest is invalid or unsafe."""


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    enabled: bool
    capabilities: tuple[str, ...]
    path: str


def validate_manifest(raw: dict[str, Any], path: str | Path = "<memory>") -> PluginManifest:
    name = str(raw.get("name", "")).strip()
    version = str(raw.get("version", "")).strip()
    enabled = bool(raw.get("enabled", True))
    capabilities_raw = raw.get("capabilities", [])

    if not name:
        raise PluginError("plugin name is required")
    if not version:
        raise PluginError("plugin version is required")
    if not isinstance(capabilities_raw, list) or not all(isinstance(item, str) for item in capabilities_raw):
        raise PluginError("plugin capabilities must be a list of strings")

    capabilities = tuple(capabilities_raw)
    forbidden = sorted(set(capabilities) & FORBIDDEN_CAPABILITIES)
    if forbidden:
        raise PluginError(f"forbidden plugin capabilities: {', '.join(forbidden)}")

    unknown = sorted(set(capabilities) - ALLOWED_CAPABILITIES)
    if unknown:
        raise PluginError(f"unknown plugin capabilities: {', '.join(unknown)}")

    return PluginManifest(name=name, version=version, enabled=enabled, capabilities=capabilities, path=str(path))


def load_plugin_manifest(path: str | Path) -> PluginManifest:
    manifest_path = Path(path)
    if manifest_path.name != "plugin.json":
        raise PluginError("plugin manifest file must be named plugin.json")
    with manifest_path.open("r", encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, dict):
        raise PluginError("plugin manifest must be a JSON object")
    return validate_manifest(raw, manifest_path)


def discover_plugins(plugins_dir: str | Path = PLUGINS_DIR) -> list[PluginManifest]:
    root = Path(plugins_dir)
    if not root.exists():
        return []
    manifests: list[PluginManifest] = []
    for manifest_path in sorted(root.glob("*/plugin.json")):
        manifests.append(load_plugin_manifest(manifest_path))
    return manifests


def plugin_can_request_send(manifest: PluginManifest) -> bool:
    """Plugins cannot directly send; all future sends must use core safety services."""
    return False
