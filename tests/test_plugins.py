import json
from pathlib import Path

import pytest

from src.plugins import PluginError, discover_plugins, load_plugin_manifest, plugin_can_request_send, validate_manifest


def test_validate_manifest_accepts_allowed_capabilities() -> None:
    manifest = validate_manifest(
        {
            "name": "templates",
            "version": "0.1.0",
            "enabled": True,
            "capabilities": ["template_provider", "reminder_rule"],
        }
    )

    assert manifest.name == "templates"
    assert manifest.capabilities == ("template_provider", "reminder_rule")


def test_validate_manifest_rejects_forbidden_send_capability() -> None:
    with pytest.raises(PluginError, match="forbidden plugin capabilities"):
        validate_manifest(
            {
                "name": "unsafe",
                "version": "0.1.0",
                "enabled": True,
                "capabilities": ["direct_send"],
            }
        )


def test_validate_manifest_rejects_unknown_capability() -> None:
    with pytest.raises(PluginError, match="unknown plugin capabilities"):
        validate_manifest(
            {
                "name": "unknown",
                "version": "0.1.0",
                "enabled": True,
                "capabilities": ["network_sync"],
            }
        )


def test_discover_plugins_loads_local_plugin_json(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "sample"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "sample",
                "version": "0.1.0",
                "enabled": True,
                "capabilities": ["template_provider"],
            }
        ),
        encoding="utf-8",
    )

    manifests = discover_plugins(tmp_path)

    assert len(manifests) == 1
    assert manifests[0].name == "sample"


def test_load_plugin_manifest_requires_plugin_json_name(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(PluginError, match="plugin.json"):
        load_plugin_manifest(path)


def test_plugin_cannot_request_direct_send() -> None:
    manifest = validate_manifest(
        {
            "name": "sample",
            "version": "0.1.0",
            "enabled": True,
            "capabilities": ["template_provider"],
        }
    )

    assert plugin_can_request_send(manifest) is False
