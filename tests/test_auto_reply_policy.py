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


def make_config(owner_status="offline", owner_overrides=None, **auto_reply_overrides):
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


def test_delay_minutes_keeps_event_pending_before_window_expires():
    policy = AutoReplyPolicy(
        make_config(delay_minutes=5, owner_overrides={"offline_reply_immediate": False})
    )

    event = policy.evaluate(make_event(), now=BASE_TIME + timedelta(minutes=4, seconds=59))

    assert event.status == "pending"
    assert event.reason == "waiting for owner response window"


def test_event_becomes_ready_after_delay_minutes():
    policy = AutoReplyPolicy(
        make_config(delay_minutes=5, owner_overrides={"offline_reply_immediate": False})
    )

    event = policy.evaluate(make_event(), now=BASE_TIME + timedelta(minutes=5))

    assert event.status == "ready_for_reply"


def test_online_owner_ignores_candidate_with_owner_online_reason():
    policy = AutoReplyPolicy(make_config(owner_status="online", delay_minutes=0))

    event = policy.evaluate(make_event(), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "owner_online"


def test_offline_owner_replies_immediately_without_delay():
    policy = AutoReplyPolicy(make_config(owner_status="offline", delay_minutes=5))

    event = policy.evaluate(make_event(first_seen_at=BASE_TIME), now=BASE_TIME)

    assert event.status == "ready_for_reply"


def test_cooldown_prevents_repeated_reply_plan_for_same_sender():
    policy = AutoReplyPolicy(make_config(delay_minutes=0, cooldown_minutes=60))

    first = policy.evaluate(make_event(), now=BASE_TIME)
    second = policy.evaluate(make_event(detected_at=BASE_TIME + timedelta(minutes=10)), now=BASE_TIME + timedelta(minutes=10))

    assert first.status == "ready_for_reply"
    assert second.status == "ignored"
    assert second.reason == "cooldown active for sender"


def test_blocklist_filtering_ignores_group_and_system_names():
    policy = AutoReplyPolicy(make_config(delay_minutes=0))

    event = policy.evaluate(make_event(sender="同学群"), now=BASE_TIME)

    assert event.status == "ignored"
    assert "blocklist" in (event.reason or "")


def test_private_whitelist_allows_test_user_ai():
    classification = classify_chat_sender("爱", auto_reply_config(make_config()))

    assert classification.is_private is True
    assert classification.reason is None
    assert classification.matched_whitelist == "爱"


def test_non_whitelisted_sender_is_not_treated_as_private():
    policy = AutoReplyPolicy(make_config(delay_minutes=0))

    event = policy.evaluate(make_event(sender="Alice"), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "sender not in private chat whitelist"


def test_group_keyword_overrides_whitelist_for_safety():
    config = make_config(private_chat_whitelist=["同学群"])
    policy = AutoReplyPolicy(config)

    event = policy.evaluate(make_event(sender="同学群"), now=BASE_TIME)

    assert event.status == "ignored"
    assert "blocklist" in (event.reason or "")


def test_private_only_filtering_ignores_non_private_candidate():
    policy = AutoReplyPolicy(make_config(delay_minutes=0, private_only=True))

    event = policy.evaluate(make_event(is_private_candidate=False), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "private_only policy rejected candidate"


def test_low_ocr_confidence_filtering_ignores_candidate():
    policy = AutoReplyPolicy(make_config(delay_minutes=0, min_ocr_confidence=0.65))

    event = policy.evaluate(make_event(confidence=0.4), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "OCR confidence below minimum"


def test_unknown_sender_filtering_ignores_candidate():
    policy = AutoReplyPolicy(make_config(delay_minutes=0))

    event = policy.evaluate(make_event(sender="unknown"), now=BASE_TIME)

    assert event.status == "ignored"
    assert event.reason == "unknown sender"


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
