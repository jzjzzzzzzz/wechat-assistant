"""Dry-run auto-reply daemon orchestration."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import datetime
from typing import Any, Callable

from src.auto_reply_policy import (
    AutoReplyEvent,
    AutoReplyPolicy,
    auto_reply_config,
    dry_run_action_text,
    validate_auto_reply_config,
)
from src.auto_reply_state import AutoReplyStateStore
from src.notification_listener import detect_notification_events
from src.owner_status import get_owner_status, owner_config
from src.unread_scanner import scan_unread_events


LOGGER = logging.getLogger(__name__)


Detector = Callable[[dict[str, Any]], list[AutoReplyEvent]]


def _force_dry_run(config: dict[str, Any]) -> dict[str, Any]:
    copied = dict(config)
    ar = auto_reply_config(copied)
    ar["dry_run"] = True
    copied["auto_reply"] = ar
    copied["dry_run"] = True
    copied["allow_real_send"] = False
    return copied


class AutoReplyDaemon:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        notification_detector: Detector = detect_notification_events,
        unread_scanner: Detector = scan_unread_events,
        sleep_func: Callable[[float], None] = time.sleep,
        now_func: Callable[[], datetime] = datetime.now,
        state_store: AutoReplyStateStore | None = None,
    ) -> None:
        self.config = _force_dry_run(config)
        self.auto_reply_config = validate_auto_reply_config(self.config)
        self.notification_detector = notification_detector
        self.unread_scanner = unread_scanner
        self.sleep_func = sleep_func
        self.now_func = now_func
        self.policy = AutoReplyPolicy(self.config, now_func=now_func)
        self.state_store = state_store or AutoReplyStateStore(self.config.get("database_path"))
        self.database_path = str(self.state_store.database_path)
        self._events_by_key: dict[tuple[str, str], AutoReplyEvent] = {}

    def _merge_seen(self, events: list[AutoReplyEvent]) -> list[AutoReplyEvent]:
        merged: list[AutoReplyEvent] = []
        for event in events:
            key = (event.source, event.sender)
            previous = self._events_by_key.get(key)
            if previous is None:
                self._events_by_key[key] = event
                merged.append(event)
                continue

            updated = replace(
                event,
                first_seen_at=previous.first_seen_at,
                last_seen_at=event.detected_at,
                status=previous.status if previous.status == "ready_for_reply" else event.status,
            )
            self._events_by_key[key] = updated
            merged.append(updated)
        return merged

    def detection_pass(self) -> list[AutoReplyEvent]:
        events: list[AutoReplyEvent] = []
        priority = list(self.auto_reply_config.get("detection_priority", []))
        for source in priority:
            try:
                if source == "notification_ocr":
                    detected = self.notification_detector(self.config)
                elif source == "unread_chat_scan":
                    detected = self.unread_scanner(self.config)
                else:
                    LOGGER.warning("Unknown auto-reply detection source ignored: %s", source)
                    continue
                LOGGER.info("Auto-reply detection source=%s candidates=%s", source, len(detected))
                events.extend(detected)
            except Exception as exc:
                LOGGER.error("Auto-reply detection source=%s failed safely: %s", source, exc)
        return self._merge_seen(events)

    def _merge_sources_by_sender(self, events: list[AutoReplyEvent]) -> list[AutoReplyEvent]:
        priority = {str(source): index for index, source in enumerate(self.auto_reply_config.get("detection_priority", []))}
        grouped: dict[str, list[AutoReplyEvent]] = {}
        for event in events:
            grouped.setdefault(event.sender, []).append(event)

        merged_events: list[AutoReplyEvent] = []
        for sender, items in grouped.items():
            ordered = sorted(
                items,
                key=lambda event: (
                    priority.get(event.source, len(priority)),
                    -event.confidence,
                    event.detected_at,
                ),
            )
            best = ordered[0]
            first_seen_at = min(item.first_seen_at for item in items)
            last_seen_at = max(item.last_seen_at for item in items)
            last_replied_at = max(
                (item.last_replied_at for item in items if item.last_replied_at is not None),
                default=None,
            )
            merged_events.append(
                replace(
                    best,
                    first_seen_at=first_seen_at,
                    last_seen_at=last_seen_at,
                    last_replied_at=last_replied_at,
                )
            )
        return sorted(merged_events, key=lambda event: (event.detected_at, event.sender))

    def _persist_and_plan(self, events: list[AutoReplyEvent]) -> list[AutoReplyEvent]:
        now = self.now_func()
        stale_after_minutes = float(self.auto_reply_config.get("state_stale_minutes", 1440))
        cooldown_minutes = float(self.auto_reply_config.get("cooldown_minutes", 60))
        merged_events: list[AutoReplyEvent] = []
        for event in events:
            merged = self.state_store.merge_detected_event(
                event,
                now=now,
                cooldown_minutes=cooldown_minutes,
                stale_after_minutes=stale_after_minutes,
            )
            merged_events.append(merged)
        merged_events = self._merge_sources_by_sender(merged_events)
        planned = self.policy.plan_actions(merged_events, now=now)
        for event in planned:
            self.state_store.upsert_event_state(
                event,
                now=now,
                cooldown_minutes=cooldown_minutes,
                stale_after_minutes=stale_after_minutes,
            )
        self.state_store.mark_stale_rows(now=now, stale_after_minutes=stale_after_minutes)
        return planned

    def run_once(self) -> list[AutoReplyEvent]:
        owner_record = get_owner_status(self.config)
        self.config["owner_status"] = owner_record.status
        self.policy = AutoReplyPolicy(self.config, now_func=self.now_func)
        LOGGER.info(
            "Auto-reply dry-run pass starting. enabled=%s dry_run=%s allow_real_send=%s owner_status=%s",
            self.auto_reply_config.get("enabled"),
            self.auto_reply_config.get("dry_run"),
            self.config.get("allow_real_send", False),
            owner_record.status,
        )
        LOGGER.info(
            "Owner status source=%s updated_at=%s",
            owner_record.source,
            owner_record.updated_at.isoformat(timespec="seconds") if owner_record.updated_at else "none",
        )
        LOGGER.info("Auto-reply state database: %s", self.database_path)
        detected = self.detection_pass()
        LOGGER.info("Auto-reply detected candidate count=%s", len(detected))
        planned = self._persist_and_plan(detected)
        pending_count = sum(1 for event in planned if event.status == "pending")
        ready_count = sum(1 for event in planned if event.status == "ready_for_reply")
        ignored_count = sum(1 for event in planned if event.status == "ignored")
        would_auto_reply = ready_count > 0
        LOGGER.info(
            "Auto-reply planning summary detected=%s pending=%s ready_for_reply=%s ignored=%s",
            len(detected),
            pending_count,
            ready_count,
            ignored_count,
        )
        LOGGER.info("Auto-reply WOULD AUTO REPLY emitted=%s", would_auto_reply)
        for event in planned:
            elapsed_seconds = max(0.0, (event.detected_at - event.first_seen_at).total_seconds())
            delay_seconds = float(self.auto_reply_config.get("delay_minutes", 5)) * 60.0
            LOGGER.info(
                "Auto-reply state sender=%s source=%s status=%s first_seen_at=%s elapsed_seconds=%.0f delay_seconds=%.0f reason=%s",
                event.sender,
                event.source,
                event.status,
                event.first_seen_at.isoformat(timespec="seconds"),
                elapsed_seconds,
                delay_seconds,
                event.reason,
            )
            if event.status == "ready_for_reply":
                LOGGER.info(
                    "WOULD AUTO REPLY Target=%s Message=%s",
                    event.sender,
                    self.auto_reply_config["reply_message"],
                )
            else:
                LOGGER.info(
                    "Auto-reply candidate status=%s sender=%s reason=%s",
                    event.status,
                    event.sender,
                    event.reason,
                )
        return planned

    def run_forever(self) -> None:
        interval = float(self.auto_reply_config.get("poll_interval_seconds", 5))
        LOGGER.info("Auto-reply daemon polling every %.2f seconds.", interval)
        try:
            while True:
                self.run_once()
                self.sleep_func(interval)
        except KeyboardInterrupt:
            LOGGER.info("Auto-reply daemon stopped by Ctrl+C.")
        finally:
            self.state_store.close()


def print_auto_reply_plan(config: dict[str, Any]) -> None:
    ar = auto_reply_config(config)
    owner_record = get_owner_status(config)
    owner = owner_config(config)
    unread = config.get("unread_scan", {}) if isinstance(config.get("unread_scan"), dict) else {}
    auto_reply_allowed = (
        owner_record.status == "offline"
        and bool(ar.get("dry_run", True))
        and not bool(config.get("allow_real_send", False))
    )
    print("Auto-reply config:")
    for key in (
        "enabled",
        "dry_run",
        "delay_minutes",
        "poll_interval_seconds",
        "cooldown_minutes",
        "state_stale_minutes",
        "private_only",
        "require_private_chat_whitelist",
        "reply_message",
        "min_ocr_confidence",
    ):
        print(f"  {key}: {ar.get(key)}")
    print("Private chat whitelist:")
    private_whitelist = ar.get("private_chat_whitelist", [])
    if private_whitelist:
        for sender in private_whitelist:
            print(f"  - {sender}")
    else:
        print("  - none")
    print("Detection priority:")
    for source in ar.get("detection_priority", []):
        print(f"  - {source}")
    print("Owner status:")
    print(f"  status: {owner_record.status}")
    print(
        "  updated_at: "
        f"{owner_record.updated_at.isoformat(timespec='seconds') if owner_record.updated_at else 'none'}"
    )
    print(f"  source: {owner_record.source}")
    print(f"  offline_reply_immediate: {owner.get('offline_reply_immediate', True)}")
    print("Safety status:")
    print(f"  dry_run: {ar.get('dry_run', True)}")
    print(f"  allow_real_send: {config.get('allow_real_send', False)}")
    print(f"  scroll_scan_default: {unread.get('enable_scroll_scan', False)}")
    print(f"  auto_reply_currently_allowed: {auto_reply_allowed}")
    print(f"State storage: {config.get('database_path', 'data/wechat_assistant.sqlite3')} (table auto_reply_state)")
    print("What will be monitored:")
    print("  - macOS WeChat notification area via screenshot/OCR")
    print("  - WeChat left chat list unread indicators as fallback")
    print("What will be ignored:")
    for keyword in ar.get("blocklist_keywords", []):
        print(f"  - {keyword}")
    print("What will never be sent in this milestone:")
    print("  - real WeChat messages")
    print("  - group chats")
    print("  - public accounts, subscriptions, service notifications, and system messages")


def run_auto_reply_once(
    config: dict[str, Any],
    *,
    notification_detector: Detector = detect_notification_events,
    unread_scanner: Detector = scan_unread_events,
) -> list[AutoReplyEvent]:
    daemon = AutoReplyDaemon(
        config,
        notification_detector=notification_detector,
        unread_scanner=unread_scanner,
    )
    try:
        return daemon.run_once()
    finally:
        daemon.state_store.close()


def print_planned_actions(events: list[AutoReplyEvent], config: dict[str, Any]) -> None:
    if not events:
        print("No auto-reply candidates detected.")
        return
    for event in events:
        print(
            f"[{event.status}] source={event.source} sender={event.sender} "
            f"confidence={event.confidence:.2f} reason={event.reason or ''}".rstrip()
        )
        if event.status == "ready_for_reply":
            print(dry_run_action_text(event, config))
