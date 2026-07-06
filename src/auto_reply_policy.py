"""Dry-run auto-reply event model and policy rules."""

from __future__ import annotations

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
    "blocklist_keywords": [
        "群聊",
        "群",
        "服务通知",
        "订阅号",
        "公众号",
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
        "blocklist_keywords": list,
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
    return ar


def should_ignore_by_name(sender: str, ar_config: dict[str, Any]) -> str | None:
    normalized = sender.strip()
    if not normalized or normalized.lower() == "unknown":
        return "unknown sender"
    for keyword in ar_config.get("blocklist_keywords", []):
        keyword_text = str(keyword).strip()
        if keyword_text and keyword_text in normalized:
            return f"sender matches blocklist keyword: {keyword_text}"
    return None


class AutoReplyPolicy:
    """Stateful policy for dry-run auto-reply planning."""

    def __init__(self, config: dict[str, Any], *, now_func: Any | None = None) -> None:
        self.config = validate_auto_reply_config(config)
        self.now_func = now_func or datetime.now
        self._last_prepared_by_sender: dict[str, datetime] = {}

    def evaluate(self, event: AutoReplyEvent, *, now: datetime | None = None) -> AutoReplyEvent:
        current_time = now or self.now_func()
        reason = should_ignore_by_name(event.sender, self.config)
        if reason:
            return replace(event, status="ignored", reason=reason)

        if event.confidence < float(self.config["min_ocr_confidence"]):
            return replace(event, status="ignored", reason="OCR confidence below minimum")

        if self.config.get("private_only", True) and not event.is_private_candidate:
            return replace(event, status="ignored", reason="private_only policy rejected candidate")

        delay = timedelta(minutes=float(self.config["delay_minutes"]))
        if current_time - event.first_seen_at < delay:
            return replace(event, status="pending", reason="waiting for owner response window")

        cooldown = timedelta(minutes=float(self.config["cooldown_minutes"]))
        last_prepared = event.last_replied_at or self._last_prepared_by_sender.get(event.sender)
        if last_prepared is not None and current_time - last_prepared < cooldown:
            return replace(event, status="ignored", reason="cooldown active for sender")

        self._last_prepared_by_sender[event.sender] = current_time
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
