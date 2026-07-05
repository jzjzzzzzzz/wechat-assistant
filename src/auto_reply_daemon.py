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
from src.notification_listener import detect_notification_events
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
    ) -> None:
        self.config = _force_dry_run(config)
        self.auto_reply_config = validate_auto_reply_config(self.config)
        self.notification_detector = notification_detector
        self.unread_scanner = unread_scanner
        self.sleep_func = sleep_func
        self.now_func = now_func
        self.policy = AutoReplyPolicy(self.config, now_func=now_func)
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

    def run_once(self) -> list[AutoReplyEvent]:
        LOGGER.info(
            "Auto-reply dry-run pass starting. enabled=%s dry_run=%s allow_real_send=%s",
            self.auto_reply_config.get("enabled"),
            self.auto_reply_config.get("dry_run"),
            self.config.get("allow_real_send", False),
        )
        events = self.detection_pass()
        planned = self.policy.plan_actions(events, now=self.now_func())
        for event in planned:
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


def print_auto_reply_plan(config: dict[str, Any]) -> None:
    ar = auto_reply_config(config)
    print("Auto-reply config:")
    for key in (
        "enabled",
        "dry_run",
        "delay_minutes",
        "poll_interval_seconds",
        "cooldown_minutes",
        "private_only",
        "reply_message",
        "min_ocr_confidence",
    ):
        print(f"  {key}: {ar.get(key)}")
    print("Detection priority:")
    for source in ar.get("detection_priority", []):
        print(f"  - {source}")
    print("Safety status:")
    print(f"  dry_run: {ar.get('dry_run', True)}")
    print(f"  allow_real_send: {config.get('allow_real_send', False)}")
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
    return daemon.run_once()


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
