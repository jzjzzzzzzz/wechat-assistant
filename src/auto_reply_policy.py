"""Dry-run auto-reply event model and policy rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Literal


AutoReplySource = Literal["notification_ocr", "unread_chat_scan"]
AutoReplyStatus = Literal["pending", "ready_for_reply", "ignored", "expired"]


DEFAULT_AUTO_REPLY_CONFIG: dict[str, Any] = {
    "enabled": False,
    "dry_run": True,
    "delay_minutes": 5,
    "poll_interval_seconds": 5,
    "cooldown_minutes": 60,
    "state_stale_minutes": 1440,
    "private_only": True,
    "reply_message": "号主不在线～ AI自动回复的",
    "detection_priority": ["notification_ocr", "unread_chat_scan"],
    "allowed_test_contacts": ["文件传输助手"],
    "require_private_chat_whitelist": True,
    "private_chat_whitelist": ["爱"],
    "blocklist_keywords": [
        "群聊",
        "群",
        "服务通知",
        "订阅号",
        "公众号",
        "微信支付",
        "微信团队",
    ],
    "non_private_keywords": [
        "Official Accounts",
        "Service Accounts",
        "Weixin Games",
        "WeChat Pay",
        "WeChat Team",
        "Subscriptions",
        "Subscription",
        "公众号",
        "订阅号",
        "服务通知",
        "微信支付",
        "微信团队",
    ],
    "min_ocr_confidence": 0.65,
}


@dataclass(frozen=True)
class AutoReplyEvent:
    source: AutoReplySource
    sender: str
    message_preview: str
    detected_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    confidence: float
    last_replied_at: datetime | None = None
    status: AutoReplyStatus = "pending"
    reason: str | None = None
    is_private_candidate: bool = True

    @property
    def known_sender(self) -> bool:
        return bool(self.sender.strip()) and self.sender.strip().lower() != "unknown"


@dataclass(frozen=True)
class ChatSenderClassification:
    sender: str
    normalized_sender: str
    is_private: bool
    reason: str | None = None
    category: str = "private"
    matched_whitelist: str | None = None
    matched_blocklist_keyword: str | None = None
    matched_non_private_keyword: str | None = None


def normalize_chat_sender(sender: str) -> str:
    cleaned = str(sender).replace("\u3000", " ")
    cleaned = cleaned.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _text_contains_keyword(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    if keyword.isascii():
        return keyword.casefold() in text.casefold()
    return keyword in text


def _looks_like_group_chat_name(sender: str) -> str | None:
    if re.search(r"[\(（\[]\s*\d+\s*人?\s*[\)）\]]$", sender):
        return "sender looks like group chat: member_count_suffix"
    if re.search(r".+\s*[、，]\s*.+", sender):
        return "sender looks like group chat: multi_participant_separator"
    if re.search(r".+\s*/\s*.+", sender):
        return "sender looks like group chat: multi_participant_separator"
    if re.search(r".+\s+&\s+.+", sender):
        return "sender looks like group chat: multi_participant_separator"
    return None


def auto_reply_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = DEFAULT_AUTO_REPLY_CONFIG.copy()
    raw = config.get("auto_reply", {})
    if isinstance(raw, dict):
        merged.update(raw)
    return merged


def validate_auto_reply_config(config: dict[str, Any]) -> dict[str, Any]:
    ar = auto_reply_config(config)
    required_types: dict[str, type | tuple[type, ...]] = {
        "enabled": bool,
        "dry_run": bool,
        "delay_minutes": (int, float),
        "poll_interval_seconds": (int, float),
        "cooldown_minutes": (int, float),
        "state_stale_minutes": (int, float),
        "private_only": bool,
        "reply_message": str,
        "detection_priority": list,
        "allowed_test_contacts": list,
        "require_private_chat_whitelist": bool,
        "private_chat_whitelist": list,
        "blocklist_keywords": list,
        "non_private_keywords": list,
        "min_ocr_confidence": (int, float),
    }
    for key, expected_type in required_types.items():
        if not isinstance(ar.get(key), expected_type):
            expected_name = (
                " or ".join(t.__name__ for t in expected_type)
                if isinstance(expected_type, tuple)
                else expected_type.__name__
            )
            raise ValueError(
                f"Invalid config key 'auto_reply.{key}': expected {expected_name}, "
                f"got {type(ar.get(key)).__name__}"
            )
    ar["delay_minutes"] = float(ar["delay_minutes"])
    ar["poll_interval_seconds"] = float(ar["poll_interval_seconds"])
    ar["cooldown_minutes"] = float(ar["cooldown_minutes"])
    ar["state_stale_minutes"] = float(ar["state_stale_minutes"])
    ar["min_ocr_confidence"] = float(ar["min_ocr_confidence"])
    if ar["delay_minutes"] < 0:
        raise ValueError("Invalid config key 'auto_reply.delay_minutes': must be >= 0")
    if ar["poll_interval_seconds"] <= 0:
        raise ValueError("Invalid config key 'auto_reply.poll_interval_seconds': must be > 0")
    if ar["cooldown_minutes"] < 0:
        raise ValueError("Invalid config key 'auto_reply.cooldown_minutes': must be >= 0")
    if ar["state_stale_minutes"] < 0:
        raise ValueError("Invalid config key 'auto_reply.state_stale_minutes': must be >= 0")
    if not 0.0 <= ar["min_ocr_confidence"] <= 1.0:
        raise ValueError("Invalid config key 'auto_reply.min_ocr_confidence': must be between 0 and 1")
    ar["private_chat_whitelist"] = [
        normalize_chat_sender(str(item))
        for item in ar.get("private_chat_whitelist", [])
        if normalize_chat_sender(str(item))
    ]
    ar["blocklist_keywords"] = [
        str(item).strip()
        for item in ar.get("blocklist_keywords", [])
        if str(item).strip()
    ]
    ar["non_private_keywords"] = [
        str(item).strip()
        for item in ar.get("non_private_keywords", [])
        if str(item).strip()
    ]
    return ar


def classify_chat_sender(sender: str, ar_config: dict[str, Any]) -> ChatSenderClassification:
    normalized = normalize_chat_sender(sender)
    if not normalized or normalized.lower() == "unknown":
        return ChatSenderClassification(sender, normalized, False, "unknown sender", category="unknown")

    for keyword in ar_config.get("blocklist_keywords", []):
        keyword_text = str(keyword).strip()
        if keyword_text and _text_contains_keyword(normalized, keyword_text):
            return ChatSenderClassification(
                sender,
                normalized,
                False,
                f"sender matches blocklist keyword: {keyword_text}",
                category="group_or_blocklisted",
                matched_blocklist_keyword=keyword_text,
            )

    for keyword in ar_config.get("non_private_keywords", []):
        keyword_text = str(keyword).strip()
        if keyword_text and _text_contains_keyword(normalized, keyword_text):
            return ChatSenderClassification(
                sender,
                normalized,
                False,
                f"sender matches non-private keyword: {keyword_text}",
                category="non_private",
                matched_non_private_keyword=keyword_text,
            )

    group_reason = _looks_like_group_chat_name(normalized)
    if group_reason:
        return ChatSenderClassification(
            sender,
            normalized,
            False,
            group_reason,
            category="group_candidate",
        )

    if bool(ar_config.get("require_private_chat_whitelist", True)):
        whitelist = [
            normalize_chat_sender(str(item))
            for item in ar_config.get("private_chat_whitelist", [])
            if normalize_chat_sender(str(item))
        ]
        matched_whitelist = next(
            (item for item in whitelist if item.casefold() == normalized.casefold()),
            None,
        )
        if matched_whitelist is None:
            return ChatSenderClassification(
                sender,
                normalized,
                False,
                "sender not in private chat whitelist",
                category="not_whitelisted",
            )
        return ChatSenderClassification(
            sender,
            normalized,
            True,
            category="private",
            matched_whitelist=matched_whitelist,
        )

    return ChatSenderClassification(sender, normalized, True, category="private")


def should_ignore_by_name(sender: str, ar_config: dict[str, Any]) -> str | None:
    return classify_chat_sender(sender, ar_config).reason


def _current_owner_status(config: dict[str, Any]) -> str:
    """Return current system status: 'online' (active/OL) or 'offline' (inactive/OFF) or 'unknown'.

    Semantics (aligned with macOS top-right corner label):
    - 'online' / OL (green)  → auto-reply system is ACTIVE  → reply IS allowed
    - 'offline' / OFF (red)  → auto-reply system is INACTIVE → reply is BLOCKED
    - 'unknown'              → cannot determine              → reply is BLOCKED (safe default)
    """
    status = str(config.get("owner_status", "")).strip().lower()
    if status in {"online", "offline", "unknown"}:
        return status
    owner = config.get("owner", {})
    if isinstance(owner, dict):
        default_status = str(owner.get("status_default", "online")).strip().lower()
        if default_status in {"online", "offline"}:
            return default_status
    return "unknown"


def _immediate_reply_when_online(config: dict[str, Any]) -> bool:
    """When system is online (OL), skip the delay window and reply immediately."""
    owner = config.get("owner", {})
    if isinstance(owner, dict):
        # offline_reply_immediate key kept for config backward-compat; semantically now means
        # 'when the system is active/online, reply without waiting the delay window'
        return bool(owner.get("offline_reply_immediate", True))
    return True


class AutoReplyPolicy:
    """Stateful policy for auto-reply planning.

    Decision flow per event:
      1. system_status == 'online' (OL)? → proceed
         system_status == 'offline' (OFF) or 'unknown'? → block (ignored)
      2. sender not blocklisted / not group / in whitelist? → proceed; else ignored
      3. OCR confidence >= threshold? → proceed; else ignored
      4. private_only and not private? → ignored
      5. delay window elapsed (or immediate mode on)? → proceed; else pending
      6. cooldown not active? → ready_for_reply; else ignored
    """

    def __init__(self, config: dict[str, Any], *, now_func: Any | None = None) -> None:
        self.config = validate_auto_reply_config(config)
        self.config["owner_status"] = config.get("owner_status")
        self.config["owner"] = config.get("owner", {})
        self.now_func = now_func or datetime.now
        self._last_prepared_by_sender: dict[str, datetime] = {}

    def evaluate(self, event: AutoReplyEvent, *, now: datetime | None = None) -> AutoReplyEvent:
        import logging
        logger = logging.getLogger(__name__)

        current_time = now or self.now_func()
        system_status = _current_owner_status(self.config)

        # Gate 1: system must be ONLINE (OL) to allow any reply
        if system_status != "online":
            reason = "system_offline" if system_status == "offline" else "system_status_unknown"
            logger.info(
                "Auto-reply blocked. sender=%s system_status=%s reason=%s",
                event.sender, system_status, reason,
            )
            return replace(event, status="ignored", reason=reason)

        logger.info(
            "Auto-reply gate passed: system_status=online. sender=%s",
            event.sender,
        )

        reason = should_ignore_by_name(event.sender, self.config)
        if reason:
            logger.info("Auto-reply blocked by sender filter. sender=%s reason=%s", event.sender, reason)
            return replace(event, status="ignored", reason=reason)

        if event.confidence < float(self.config["min_ocr_confidence"]):
            logger.info(
                "Auto-reply blocked: OCR confidence too low. sender=%s confidence=%.3f min=%.3f",
                event.sender, event.confidence, self.config["min_ocr_confidence"],
            )
            return replace(event, status="ignored", reason="OCR confidence below minimum")

        if self.config.get("private_only", True) and not event.is_private_candidate:
            logger.info("Auto-reply blocked: private_only. sender=%s", event.sender)
            return replace(event, status="ignored", reason="private_only policy rejected candidate")

        if not (system_status == "online" and _immediate_reply_when_online(self.config)):
            delay = timedelta(minutes=float(self.config["delay_minutes"]))
            if current_time - event.first_seen_at < delay:
                logger.info(
                    "Auto-reply pending: waiting delay window. sender=%s elapsed=%.0fs delay=%.0fs",
                    event.sender,
                    (current_time - event.first_seen_at).total_seconds(),
                    delay.total_seconds(),
                )
                return replace(event, status="pending", reason="waiting for owner response window")

        cooldown = timedelta(minutes=float(self.config["cooldown_minutes"]))
        last_prepared = event.last_replied_at or self._last_prepared_by_sender.get(event.sender)
        if last_prepared is not None and current_time - last_prepared < cooldown:
            logger.info("Auto-reply blocked: cooldown active. sender=%s", event.sender)
            return replace(event, status="ignored", reason="cooldown active for sender")

        self._last_prepared_by_sender[event.sender] = current_time
        logger.info("Auto-reply READY. sender=%s message=%s", event.sender, self.config.get("reply_message", ""))
        return replace(event, status="ready_for_reply", reason=None)

    def plan_actions(self, events: list[AutoReplyEvent], *, now: datetime | None = None) -> list[AutoReplyEvent]:
        return [self.evaluate(event, now=now) for event in events]


def dry_run_action_text(event: AutoReplyEvent, config: dict[str, Any]) -> str:
    ar = auto_reply_config(config)
    return (
        "WOULD AUTO REPLY\n"
        f"Target: {event.sender}\n"
        f"Message: {ar['reply_message']}"
    )
