from pathlib import Path

import yaml

from src.private_whitelist import (
    add_private_whitelist_sender,
    read_private_whitelist,
    remove_private_whitelist_sender,
)


def write_settings(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "dry_run: true",
                "allow_real_send: false",
                "auto_reply:",
                "  enabled: false",
                "  private_chat_whitelist:",
                "    - \"爱\"",
                "  blocklist_keywords:",
                "    - \"群\"",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_add_private_whitelist_sender_preserves_yaml_structure(tmp_path):
    settings = tmp_path / "settings.yaml"
    write_settings(settings)

    result = add_private_whitelist_sender("Eric D (PRISMS)", path=settings)

    assert result.action == "added"
    assert result.entries == ["爱", "Eric D (PRISMS)"]
    loaded = yaml.safe_load(settings.read_text(encoding="utf-8"))
    assert loaded["auto_reply"]["private_chat_whitelist"] == ["爱", "Eric D (PRISMS)"]
    assert loaded["auto_reply"]["blocklist_keywords"] == ["群"]


def test_add_private_whitelist_sender_is_idempotent_case_insensitive(tmp_path):
    settings = tmp_path / "settings.yaml"
    write_settings(settings)

    first = add_private_whitelist_sender("Alice", path=settings)
    second = add_private_whitelist_sender("alice", path=settings)

    assert first.action == "added"
    assert second.action == "already_present"
    assert read_private_whitelist(settings) == ["爱", "Alice"]


def test_remove_private_whitelist_sender(tmp_path):
    settings = tmp_path / "settings.yaml"
    write_settings(settings)
    add_private_whitelist_sender("Alice", path=settings)

    result = remove_private_whitelist_sender("alice", path=settings)

    assert result.action == "removed"
    assert result.entries == ["爱"]
    assert read_private_whitelist(settings) == ["爱"]


def test_remove_private_whitelist_sender_reports_not_found(tmp_path):
    settings = tmp_path / "settings.yaml"
    write_settings(settings)

    result = remove_private_whitelist_sender("Missing", path=settings)

    assert result.action == "not_found"
    assert result.entries == ["爱"]


def test_remove_last_private_whitelist_sender_writes_empty_list(tmp_path):
    settings = tmp_path / "settings.yaml"
    write_settings(settings)

    result = remove_private_whitelist_sender("爱", path=settings)

    assert result.action == "removed"
    assert result.entries == []
    loaded = yaml.safe_load(settings.read_text(encoding="utf-8"))
    assert loaded["auto_reply"]["private_chat_whitelist"] == []
