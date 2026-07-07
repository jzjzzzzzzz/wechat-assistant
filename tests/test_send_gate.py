"""Tests for src/send_gate.py — unified auto-reply safety gate.

Tests cover:
- Online status → allowed (if other conditions met)
- Offline status → blocked
- Unknown status → blocked (safe default)
- Group chat names → blocked
- 文件传输助手 → allowed as safe test target
- Unknown sender → blocked
- Low OCR confidence → blocked
- Real-send target not in whitelist → blocked
"""
from pathlib import Path

import pytest

from src.send_gate import GateDecision, should_auto_reply


def _base_config(**overrides) -> dict:
    """Minimal config with safe defaults."""
    config = {
        "dry_run": True,
        "allow_real_send": False,
        "database_path": None,  # no DB — use override_status instead
        "auto_reply": {
            "enabled": True,
            "dry_run": True,
            "delay_minutes": 0,
            "poll_interval_seconds": 5,
            "cooldown_minutes": 60,
            "state_stale_minutes": 1440,
            "private_only": True,
            "reply_message": "号主不在线～ AI自动回复的",
            "detection_priority": ["notification_ocr"],
            "allowed_test_contacts": ["文件传输助手"],
            "require_private_chat_whitelist": True,
            "private_chat_whitelist": ["爱", "文件传输助手", "File Transfer"],
            "blocklist_keywords": ["群聊", "群", "服务通知", "订阅号", "公众号"],
            "non_private_keywords": ["Official Accounts", "WeChat Pay"],
            "min_ocr_confidence": 0.65,
        },
        "allowed_real_contacts": ["文件传输助手", "File Transfer"],
    }
    config.update(overrides)
    return config


# ── Status gate ───────────────────────────────────────────────────────────────

def test_system_online_allows_whitelisted_sender():
    decision = should_auto_reply(
        "爱",
        _base_config(),
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is True
    assert decision.system_status == "online"


def test_system_offline_blocks_all_senders():
    decision = should_auto_reply(
        "爱",
        _base_config(),
        ocr_confidence=0.9,
        override_status="offline",
    )
    assert decision.allowed is False
    assert "system_offline" in decision.reason or "offline" in decision.reason


def test_system_status_unknown_blocks_all_senders():
    """Unknown status → safe default: no send."""
    decision = should_auto_reply(
        "爱",
        _base_config(),
        ocr_confidence=0.9,
        override_status="unknown",
    )
    assert decision.allowed is False
    assert "unknown" in decision.reason


# ── Group chat detection via gate ─────────────────────────────────────────────

@pytest.mark.parametrize("group_name", [
    "项目组(5)",
    "项目组（5）",
    "项目组（5人）",
    "Study Group(12)",
    "Family（8人）",
    "同学们(100)",
    "同学群",           # keyword-based
    "订阅号",           # non-private keyword
])
def test_group_chat_names_are_blocked(group_name: str):
    config = _base_config()
    # Add the name to whitelist so the whitelist gate doesn't block it first
    config["auto_reply"]["private_chat_whitelist"] = [group_name, "爱"]
    decision = should_auto_reply(
        group_name,
        config,
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is False, (
        f"Expected group '{group_name}' to be blocked but was allowed. "
        f"reason={decision.reason}"
    )


def test_individual_name_not_blocked_as_group():
    """A plain individual name must not be misidentified as a group."""
    decision = should_auto_reply(
        "爱",
        _base_config(),
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is True


def test_chinese_individual_name_not_blocked():
    config = _base_config()
    config["auto_reply"]["private_chat_whitelist"] = ["李明"]
    decision = should_auto_reply(
        "李明",
        config,
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is True


# ── 文件传输助手 safe test target ─────────────────────────────────────────────

def test_file_transfer_allowed_when_online_dry_run():
    decision = should_auto_reply(
        "文件传输助手",
        _base_config(dry_run=True),
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is True


def test_file_transfer_allowed_for_real_send_when_in_whitelist():
    config = _base_config(
        dry_run=False,
        allow_real_send=True,
        allowed_real_contacts=["文件传输助手", "File Transfer"],
    )
    config["auto_reply"]["dry_run"] = False
    decision = should_auto_reply(
        "文件传输助手",
        config,
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is True


def test_unknown_contact_blocked_for_real_send():
    """A contact not in allowed_real_contacts must be blocked for real send."""
    config = _base_config(
        dry_run=False,
        allow_real_send=True,
        allowed_real_contacts=["文件传输助手"],
    )
    config["auto_reply"]["dry_run"] = False
    # Make the sender pass whitelist and group checks
    config["auto_reply"]["private_chat_whitelist"] = ["SomeContact"]
    decision = should_auto_reply(
        "SomeContact",
        config,
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is False
    assert "real_send_target_not_allowed" in decision.reason


# ── OCR confidence ────────────────────────────────────────────────────────────

def test_low_ocr_confidence_blocks_send():
    decision = should_auto_reply(
        "爱",
        _base_config(),
        ocr_confidence=0.3,   # below min 0.65
        override_status="online",
    )
    assert decision.allowed is False
    assert "ocr_confidence" in decision.reason


def test_confidence_at_minimum_threshold_is_allowed():
    decision = should_auto_reply(
        "爱",
        _base_config(),
        ocr_confidence=0.65,  # exactly at threshold
        override_status="online",
    )
    assert decision.allowed is True


# ── Unknown sender ────────────────────────────────────────────────────────────

def test_empty_sender_is_blocked():
    decision = should_auto_reply(
        "",
        _base_config(),
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is False


def test_unknown_sender_string_is_blocked():
    decision = should_auto_reply(
        "unknown",
        _base_config(),
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.allowed is False


# ── GateDecision bool interface ───────────────────────────────────────────────

def test_gate_decision_bool_true_when_allowed():
    decision = should_auto_reply(
        "爱",
        _base_config(),
        ocr_confidence=0.9,
        override_status="online",
    )
    assert bool(decision) is True


def test_gate_decision_bool_false_when_blocked():
    decision = should_auto_reply(
        "爱",
        _base_config(),
        ocr_confidence=0.9,
        override_status="offline",
    )
    assert bool(decision) is False


# ── dry_run flag ─────────────────────────────────────────────────────────────

def test_gate_reports_dry_run_correctly():
    decision = should_auto_reply(
        "爱",
        _base_config(dry_run=True),
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.is_dry_run is True


def test_gate_reports_real_send_mode_correctly():
    config = _base_config(dry_run=False, allow_real_send=True)
    config["auto_reply"]["dry_run"] = False
    decision = should_auto_reply(
        "文件传输助手",
        config,
        ocr_confidence=0.9,
        override_status="online",
    )
    assert decision.is_dry_run is False


def test_auto_reply_dry_run_true_keeps_gate_in_dry_run_mode():
    config = _base_config(dry_run=False, allow_real_send=True)
    config["auto_reply"]["dry_run"] = True

    decision = should_auto_reply(
        "文件传输助手",
        config,
        ocr_confidence=0.9,
        override_status="online",
    )

    assert decision.allowed is True
    assert decision.is_dry_run is True


# ── DB-backed status lookup ───────────────────────────────────────────────────

def test_gate_reads_status_from_db_when_no_override(tmp_path: Path):
    from src.owner_status import OwnerStatusStore

    db_path = tmp_path / "test.sqlite3"
    config = _base_config()
    config["database_path"] = str(db_path)

    # Write "online" to DB
    with OwnerStatusStore(db_path) as store:
        store.set_status("online", updated_by="test")
        decision = should_auto_reply(
            "爱",
            config,
            ocr_confidence=0.9,
            owner_status_store=store,
        )

    assert decision.allowed is True
    assert decision.system_status == "online"


def test_gate_blocks_when_no_live_or_database_status(tmp_path: Path):
    config = _base_config()
    config["database_path"] = str(tmp_path / "empty.sqlite3")
    config["owner"] = {"status_default": "online"}

    decision = should_auto_reply(
        "爱",
        config,
        ocr_confidence=0.9,
    )

    assert decision.allowed is False
    assert decision.system_status == "unknown"
    assert "unknown" in decision.reason


def test_gate_reads_offline_from_db_and_blocks(tmp_path: Path):
    from src.owner_status import OwnerStatusStore

    db_path = tmp_path / "test.sqlite3"
    config = _base_config()
    config["database_path"] = str(db_path)

    with OwnerStatusStore(db_path) as store:
        store.set_status("offline", updated_by="test")
        decision = should_auto_reply(
            "爱",
            config,
            ocr_confidence=0.9,
            owner_status_store=store,
        )

    assert decision.allowed is False
