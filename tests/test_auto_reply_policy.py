"""Tests for auto-reply policy and chat sender classification.

Status semantics (aligned with macOS top-right corner label):
  owner_status="online"  / 🟢 OL  → system ACTIVE   → auto-reply IS allowed
  owner_status="offline" / 🔴 OFF → system INACTIVE → auto-reply BLOCKED
  owner_status="unknown"           → cannot determine → auto-reply BLOCKED (safe default)
"""
from datetime import datetime, timedelta

from src.auto_reply_policy import (
    AutoReplyEvent,
    AutoReplyPolicy,
    auto_reply_config,
    classify_chat_sender,
)
from src.config_loader import load_config


BASE_TIME = datetime(2026, 7, 5, 12, 0, 0)


def make_event(**overrides):
    values = {
        "source": "notification_ocr",
        "sender": "爱",
        "message_preview": "hello",
        "detected_at": BASE_TIME,
        "first_seen_at": BASE_TIME,
        "last_seen_at": BASE_TIME,
        "confidence": 0.95,
        "status": "pending",
        "reason": None,
        "is_private_candidate": True,
    }
    values.update(overrides)
    return AutoReplyEvent(**values)


def make_config(owner_status="online", owner_overrides=None, **auto_reply_overrides):
    """Default owner_status='online' (OL): system is active, auto-reply allowed."""
    config = load_config()
    config = dict(config)
    auto_reply = dict(config["auto_reply"])
    auto_reply.update(auto_reply_overrides)
    config["auto_reply"] = auto_reply
    owner = dict(config.get("owner", {}))
    owner.update(owner_overrides or {})
    config["owner"] = owner
    config["owner_status"] = owner_status
    return config


# ── Status gate tests ─────────────────────────────────────────────────────────

def test_system_online_OL_allows_auto_reply():
    """OL / online → system is active → auto-reply proceeds (if sender passes other gates)."""
    policy = AutoReplyPolicy(make_config(owner_status="online", delay_minutes=0))

    event = policy.evaluate(make_event(), now=BASE_TIME)

    assert event.status == "ready_for_reply"


def test_system_offline_OFF_blocks_auto_reply():
    """OFF / offline → system is inactive → auto-reply blocked."""
    policy = AutoReplyPolicy(make_config(owner_status="offline", delay_minutes=0))

    event = policy.evaluate(make_event(), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "system_offline"


def test_system_status_unknown_blocks_auto_reply():
    """Unknown status → safe default: do not send."""
    policy = AutoReplyPolicy(make_config(owner_status="unknown", delay_minutes=0))

    event = policy.evaluate(make_event(), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "system_status_unknown"


def test_missing_explicit_runtime_status_blocks_auto_reply():
    config = make_config(owner_status=None, delay_minutes=0)
    config.pop("owner_status", None)
    policy = AutoReplyPolicy(config)

    event = policy.evaluate(make_event(), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "system_status_unknown"


def test_system_offline_blocks_immediately_regardless_of_delay():
    """When system is OFF, the event is blocked immediately — delay window irrelevant."""
    policy = AutoReplyPolicy(make_config(owner_status="offline", delay_minutes=5))

    event = policy.evaluate(make_event(first_seen_at=BASE_TIME), now=BASE_TIME + timedelta(hours=1))

    assert event.status == "ignored"
    assert event.reason == "system_offline"


# ── Delay window tests ────────────────────────────────────────────────────────

def test_delay_minutes_keeps_event_pending_before_window_expires():
    policy = AutoReplyPolicy(
        make_config(owner_status="online", delay_minutes=5, owner_overrides={"offline_reply_immediate": False})
    )

    event = policy.evaluate(make_event(), now=BASE_TIME + timedelta(minutes=4, seconds=59))

    assert event.status == "pending"
    assert event.reason == "waiting for owner response window"


def test_event_becomes_ready_after_delay_minutes():
    policy = AutoReplyPolicy(
        make_config(owner_status="online", delay_minutes=5, owner_overrides={"offline_reply_immediate": False})
    )

    event = policy.evaluate(make_event(), now=BASE_TIME + timedelta(minutes=5))

    assert event.status == "ready_for_reply"


def test_immediate_mode_skips_delay_window():
    """With offline_reply_immediate=True and system online, no delay is applied."""
    policy = AutoReplyPolicy(
        make_config(owner_status="online", delay_minutes=5, owner_overrides={"offline_reply_immediate": True})
    )

    event = policy.evaluate(make_event(first_seen_at=BASE_TIME), now=BASE_TIME)

    assert event.status == "ready_for_reply"


# ── Cooldown tests ────────────────────────────────────────────────────────────

def test_cooldown_prevents_repeated_reply_plan_for_same_sender():
    policy = AutoReplyPolicy(make_config(owner_status="online", delay_minutes=0, cooldown_minutes=60))

    first = policy.evaluate(make_event(), now=BASE_TIME)
    second = policy.evaluate(
        make_event(detected_at=BASE_TIME + timedelta(minutes=10)),
        now=BASE_TIME + timedelta(minutes=10),
    )

    assert first.status == "ready_for_reply"
    assert second.status == "ignored"
    assert second.reason == "cooldown active for sender"


# ── Group chat OCR interception tests ─────────────────────────────────────────

def test_member_count_suffix_half_width_bracket_is_group():
    """项目组(5) — half-width brackets → group."""
    classification = classify_chat_sender("项目组(5)", auto_reply_config(make_config()))
    assert classification.is_private is False
    assert classification.category == "group_candidate"
    assert classification.reason == "sender looks like group chat: member_count_suffix"


def test_member_count_suffix_full_width_bracket_is_group():
    """项目组（5）— full-width brackets no 人 → group."""
    classification = classify_chat_sender("项目组（5）", auto_reply_config(make_config()))
    assert classification.is_private is False
    assert classification.category == "group_candidate"
    assert classification.reason == "sender looks like group chat: member_count_suffix"


def test_member_count_suffix_full_width_with_ren_is_group():
    """项目组（5人）— full-width brackets with 人 → group."""
    classification = classify_chat_sender("项目组（5人）", auto_reply_config(make_config()))
    assert classification.is_private is False
    assert classification.category == "group_candidate"
    assert classification.reason == "sender looks like group chat: member_count_suffix"


def test_english_group_name_with_count_is_group():
    """Study Group(12) — English group name → group."""
    classification = classify_chat_sender("Study Group(12)", auto_reply_config(make_config()))
    assert classification.is_private is False
    assert classification.category == "group_candidate"
    assert classification.reason == "sender looks like group chat: member_count_suffix"


def test_group_name_with_number_and_words_inside_parentheses_is_group():
    """Study Group(12 members) — bracket contains a number → group."""
    classification = classify_chat_sender("Study Group(12 members)", auto_reply_config(make_config()))
    assert classification.is_private is False
    assert classification.category == "group_candidate"
    assert classification.reason == "sender looks like group chat: member_count_suffix"


def test_group_name_with_chinese_words_and_number_inside_parentheses_is_group():
    """项目组（第5组）— bracket contains a number → group."""
    classification = classify_chat_sender("项目组（第5组）", auto_reply_config(make_config()))
    assert classification.is_private is False
    assert classification.category == "group_candidate"
    assert classification.reason == "sender looks like group chat: member_count_suffix"


def test_mixed_language_group_with_full_width_ren_is_group():
    """Family（8人）— mixed brackets → group."""
    classification = classify_chat_sender("Family（8人）", auto_reply_config(make_config()))
    assert classification.is_private is False
    assert classification.category == "group_candidate"
    assert classification.reason == "sender looks like group chat: member_count_suffix"


def test_large_member_count_is_group():
    """同学们(100) — three-digit count → group."""
    classification = classify_chat_sender("同学们(100)", auto_reply_config(make_config()))
    assert classification.is_private is False
    assert classification.category == "group_candidate"


def test_individual_name_not_misidentified_as_group():
    """Plain personal name should NOT be flagged as group."""
    config = make_config(private_chat_whitelist=["Alice"], require_private_chat_whitelist=True)
    classification = classify_chat_sender("Alice", auto_reply_config(config))
    assert classification.is_private is True
    assert classification.category == "private"


def test_chinese_individual_name_not_misidentified_as_group():
    """Chinese personal name without brackets should NOT be a group."""
    config = make_config(private_chat_whitelist=["李明"], require_private_chat_whitelist=True)
    classification = classify_chat_sender("李明", auto_reply_config(config))
    assert classification.is_private is True
    assert classification.category == "private"


def test_name_with_non_numeric_parentheses_not_group():
    """Tom (Engineer) — parentheses but no number → not a group."""
    config = make_config(private_chat_whitelist=["Tom (Engineer)"], require_private_chat_whitelist=True)
    classification = classify_chat_sender("Tom (Engineer)", auto_reply_config(config))
    # 'Engineer' is not digits, so should NOT match group pattern
    assert classification.category != "group_candidate"


def test_ocr_name_with_non_numeric_parentheses_not_group_when_whitelisted():
    config = make_config(private_chat_whitelist=["Eric D (PRISMS)"], require_private_chat_whitelist=True)
    classification = classify_chat_sender("Eric D (PRISMS)", auto_reply_config(config))

    assert classification.is_private is True
    assert classification.category == "private"


def test_group_blocked_by_policy_even_if_in_whitelist():
    """Group chat name in whitelist must still be blocked — group detection takes priority."""
    config = make_config(owner_status="online", private_chat_whitelist=["同学群"])
    policy = AutoReplyPolicy(config)

    event = policy.evaluate(make_event(sender="同学群"), now=BASE_TIME)

    assert event.status == "ignored"
    assert "blocklist" in (event.reason or "")


def test_group_with_count_blocked_by_policy():
    """Group with member count in name must be blocked by policy."""
    config = make_config(owner_status="online", private_chat_whitelist=["项目组(5)"])
    policy = AutoReplyPolicy(config)

    event = policy.evaluate(make_event(sender="项目组(5)"), now=BASE_TIME)

    assert event.status == "ignored"


# ── Blocklist / non-private keyword tests ────────────────────────────────────

def test_blocklist_filtering_ignores_group_and_system_names():
    policy = AutoReplyPolicy(make_config(owner_status="online", delay_minutes=0))

    event = policy.evaluate(make_event(sender="同学群"), now=BASE_TIME)

    assert event.status == "ignored"
    assert "blocklist" in (event.reason or "")


def test_non_private_keyword_matching_is_case_insensitive():
    classification = classify_chat_sender("official accounts", auto_reply_config(make_config()))

    assert classification.is_private is False
    assert classification.category == "non_private"
    assert classification.matched_non_private_keyword == "Official Accounts"


# ── Whitelist tests ───────────────────────────────────────────────────────────

def test_private_whitelist_allows_test_user_ai():
    classification = classify_chat_sender("爱", auto_reply_config(make_config()))

    assert classification.is_private is True
    assert classification.reason is None
    assert classification.category == "private"
    assert classification.matched_whitelist == "爱"


def test_non_whitelisted_sender_is_not_treated_as_private():
    policy = AutoReplyPolicy(make_config(owner_status="online", delay_minutes=0))

    event = policy.evaluate(make_event(sender="Alice"), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "sender not in private chat whitelist"


def test_private_whitelist_matching_is_case_insensitive_for_english_names():
    config = make_config(private_chat_whitelist=["Alice"])

    classification = classify_chat_sender("alice", auto_reply_config(config))

    assert classification.is_private is True
    assert classification.matched_whitelist == "Alice"


def test_allowed_test_contacts_are_treated_as_private_test_targets():
    config = make_config(private_chat_whitelist=["爱"], allowed_test_contacts=["文件传输助手"])

    classification = classify_chat_sender("文件传输助手", auto_reply_config(config))

    assert classification.is_private is True
    assert classification.category == "private"
    assert classification.matched_whitelist == "文件传输助手"


def test_group_like_allowed_test_contact_is_still_blocked():
    config = make_config(private_chat_whitelist=["爱"], allowed_test_contacts=["测试群(5)"])

    classification = classify_chat_sender("测试群(5)", auto_reply_config(config))

    assert classification.is_private is False
    assert classification.category in {"group_or_blocklisted", "group_candidate"}


def test_multi_participant_separator_marks_sender_as_group_candidate():
    config = make_config(private_chat_whitelist=["Alice、Bob"])

    classification = classify_chat_sender("Alice、Bob", auto_reply_config(config))

    assert classification.is_private is False
    assert classification.category == "group_candidate"
    assert classification.reason == "sender looks like group chat: multi_participant_separator"


# ── OCR confidence and private-only tests ────────────────────────────────────

def test_private_only_filtering_ignores_non_private_candidate():
    policy = AutoReplyPolicy(make_config(owner_status="online", delay_minutes=0, private_only=True))

    event = policy.evaluate(make_event(is_private_candidate=False), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "private_only policy rejected candidate"


def test_low_ocr_confidence_filtering_ignores_candidate():
    policy = AutoReplyPolicy(make_config(owner_status="online", delay_minutes=0, min_ocr_confidence=0.65))

    event = policy.evaluate(make_event(confidence=0.4), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "OCR confidence below minimum"


def test_unknown_sender_filtering_ignores_candidate():
    policy = AutoReplyPolicy(make_config(owner_status="online", delay_minutes=0))

    event = policy.evaluate(make_event(sender="unknown"), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "unknown sender"


# ── Safe default config tests ────────────────────────────────────────────────

def test_config_defaults_include_safe_auto_reply_values():
    config = load_config()
    ar = auto_reply_config(config)

    assert ar["enabled"] is False
    assert ar["dry_run"] is True
    assert ar["delay_minutes"] == 5.0
    assert ar["cooldown_minutes"] == 60.0
    assert ar["state_stale_minutes"] == 1440.0
    assert ar["private_only"] is True
    assert ar["require_private_chat_whitelist"] is True
    assert "爱" in ar["private_chat_whitelist"]
    assert ar["reply_message"] == "号主不在线～ AI自动回复的"
    assert config["allow_real_send"] is False
