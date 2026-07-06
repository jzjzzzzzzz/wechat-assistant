"""Auto-reply daemon orchestration.

Long-running daemon that:
1. Polls the macOS top-right corner via OCR to track OL/OFF status changes.
2. Scans WeChat for unread messages / notification events.
3. Passes every reply candidate through should_auto_reply() safety gate.
4. In dry-run mode: logs what WOULD be sent without touching WeChat UI.
5. In real-send mode: calls send_message() only when ALL gate checks pass.

Status semantics:
  OL  / online  → auto-reply system ACTIVE  → sending allowed
  OFF / offline → auto-reply system INACTIVE → no sending
  unknown       → cannot determine           → safe default: no send
"""

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
from src.macos_status_detector import MacosStatusWatcher
from src.notification_listener import detect_notification_events
from src.owner_status import OwnerStatusStore, get_owner_status, owner_config
from src.send_gate import GateDecision, log_send_decision, should_auto_reply
from src.unread_scanner import scan_unread_events


LOGGER = logging.getLogger(__name__)

Detector = Callable[[dict[str, Any]], list[AutoReplyEvent]]


def _apply_dry_run(config: dict[str, Any]) -> dict[str, Any]:
    copied = dict(config)
    ar = auto_reply_config(copied)
    ar["dry_run"] = True
    copied["auto_reply"] = ar
    copied["dry_run"] = True
    copied["allow_real_send"] = False
    return copied


class AutoReplyDaemon:
    """Long-running auto-reply daemon.

    Pass dry_run_mode=True (default) to keep the daemon in safe dry-run mode.
    Set dry_run_mode=False only when you also set allow_real_send=True in config.
    """

    def __init__(
        self,
        config: dict[str, Any],
        *,
        dry_run_mode: bool = True,
        notification_detector: Detector = detect_notification_events,
        unread_scanner: Detector = scan_unread_events,
        sleep_func: Callable[[float], None] = time.sleep,
        now_func: Callable[[], datetime] = datetime.now,
        state_store: AutoReplyStateStore | None = None,
        status_watcher: MacosStatusWatcher | None = None,
        owner_status_store: OwnerStatusStore | None = None,
    ) -> None:
        if dry_run_mode:
            self.config = _apply_dry_run(config)
        else:
            self.config = dict(config)

        self.dry_run_mode = dry_run_mode
        self.auto_reply_config = validate_auto_reply_config(self.config)
        self.notification_detector = notification_detector
        self.unread_scanner = unread_scanner
        self.sleep_func = sleep_func
        self.now_func = now_func
        self.policy = AutoReplyPolicy(self.config, now_func=now_func)
        self.state_store = state_store or AutoReplyStateStore(self.config.get("database_path"))
        self.database_path = str(self.state_store.database_path)
        self._events_by_key: dict[tuple[str, str], AutoReplyEvent] = {}

        # Status watcher: polls macOS top-right corner each pass.
        self._status_watcher = status_watcher or MacosStatusWatcher(
            self.config,
            store=owner_status_store or OwnerStatusStore(self.config.get("database_path")),
        )

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
        priority = {
            str(source): index
            for index, source in enumerate(self.auto_reply_config.get("detection_priority", []))
        }
        grouped: dict[str, list[AutoReplyEvent]] = {}
        for event in events:
            grouped.setdefault(event.sender, []).append(event)

        merged_events: list[AutoReplyEvent] = []
        for sender, items in grouped.items():
            ordered = sorted(
                items,
                key=lambda e: (priority.get(e.source, len(priority)), -e.confidence, e.detected_at),
            )
            best = ordered[0]
            first_seen_at = min(item.first_seen_at for item in items)
            last_seen_at = max(item.last_seen_at for item in items)
            last_replied_at = max(
                (item.last_replied_at for item in items if item.last_replied_at is not None),
                default=None,
            )
            merged_events.append(replace(
                best,
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
                last_replied_at=last_replied_at,
            ))
        return sorted(merged_events, key=lambda e: (e.detected_at, e.sender))

    def _merge_state_and_plan(self, events: list[AutoReplyEvent]) -> list[AutoReplyEvent]:
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
        return self.policy.plan_actions(merged_events, now=now)

    def _persist_planned_events(self, events: list[AutoReplyEvent]) -> None:
        now = self.now_func()
        stale_after_minutes = float(self.auto_reply_config.get("state_stale_minutes", 1440))
        cooldown_minutes = float(self.auto_reply_config.get("cooldown_minutes", 60))
        for event in events:
            self.state_store.upsert_event_state(
                event,
                now=now,
                cooldown_minutes=cooldown_minutes,
                stale_after_minutes=stale_after_minutes,
            )
        self.state_store.mark_stale_rows(now=now, stale_after_minutes=stale_after_minutes)

    def _execute_reply(self, event: AutoReplyEvent) -> tuple[bool, GateDecision]:
        """Send the auto-reply for *event* after final gate validation.

        Returns (True, decision) if the message was sent (or dry-run logged).
        """
        reply_message = str(self.auto_reply_config.get("reply_message", "号主不在线～ AI自动回复的"))

        # Final status refresh immediately before sending; this prevents stale DB
        # state from authorizing a send when top-right OCR is now unknown/offline.
        current_status = self._poll_and_update_status()
        decision: GateDecision = should_auto_reply(
            event.sender,
            self.config,
            ocr_confidence=event.confidence,
            owner_status_store=getattr(self._status_watcher, "store", None),
            override_status=current_status,
        )
        log_send_decision(decision, message=reply_message)

        if not decision.allowed:
            LOGGER.info(
                "Auto-reply final gate blocked. sender=%s reason=%s",
                event.sender, decision.reason,
            )
            return False, decision

        if self.dry_run_mode:
            LOGGER.info(
                "DRY RUN: WOULD AUTO REPLY. sender=%s message=%r",
                event.sender, reply_message,
            )
            print(f"[DRY RUN] WOULD AUTO REPLY → {event.sender}: {reply_message}")
            return True, decision

        # Real send: import lazily so tests without pyautogui still work.
        try:
            from src.message_sender import send_message

            LOGGER.warning(
                "REAL AUTO REPLY. sender=%s message=%r system_status=%s",
                event.sender, reply_message, decision.system_status,
            )
            sent = send_message(self.config, event.sender, reply_message)
            if sent:
                LOGGER.info("Auto-reply sent successfully. sender=%s", event.sender)
            else:
                LOGGER.error("Auto-reply send_message returned False. sender=%s", event.sender)
            return sent, decision
        except Exception as exc:
            LOGGER.error("Auto-reply send failed for sender=%s: %s", event.sender, exc)
            return False, decision

    def _poll_and_update_status(self) -> str:
        """Poll macOS top-right corner and update owner_status in self.config."""
        try:
            detection = self._status_watcher.poll()
            if detection.raw_status != "unknown":
                self.config["owner_status"] = detection.db_status
            else:
                # Safe default: do not use a stale DB value when live OCR is unknown.
                self.config["owner_status"] = "unknown"
            return self.config["owner_status"]
        except Exception as exc:
            LOGGER.error("Status poll failed: %s — forcing status=unknown safe default", exc)
            self.config["owner_status"] = "unknown"
            return "unknown"

    def run_once(self) -> list[AutoReplyEvent]:
        # ── Step 1: refresh system status from macOS top-right corner ────────
        current_status = self._poll_and_update_status()
        self.policy = AutoReplyPolicy(self.config, now_func=self.now_func)

        LOGGER.info(
            "Daemon pass: system_status=%s dry_run=%s allow_real_send=%s",
            current_status,
            self.config.get("dry_run", True),
            self.config.get("allow_real_send", False),
        )
        LOGGER.info("Auto-reply state database: %s", self.database_path)

        # ── Step 2: detect unread / notification events ───────────────────────
        detected = self.detection_pass()
        LOGGER.info("Detected candidate count=%s", len(detected))

        # ── Step 3: planning ──────────────────────────────────────────────────
        planned = self._merge_state_and_plan(detected)

        pending_count = sum(1 for e in planned if e.status == "pending")
        ready_count = sum(1 for e in planned if e.status == "ready_for_reply")
        ignored_count = sum(1 for e in planned if e.status == "ignored")

        LOGGER.info(
            "Planning: pending=%s ready=%s ignored=%s",
            pending_count, ready_count, ignored_count,
        )

        # ── Step 4: final gate + action on ready events ───────────────────────
        finalized: list[AutoReplyEvent] = []
        for event in planned:
            delay_seconds = float(self.auto_reply_config.get("delay_minutes", 5)) * 60.0
            elapsed = max(0.0, (event.detected_at - event.first_seen_at).total_seconds())
            LOGGER.info(
                "Event: sender=%s source=%s status=%s elapsed=%.0fs delay=%.0fs reason=%s",
                event.sender, event.source, event.status, elapsed, delay_seconds, event.reason,
            )

            if event.status == "ready_for_reply":
                executed, decision = self._execute_reply(event)
                if not executed:
                    event = replace(event, status="ignored", reason=decision.reason)
            finalized.append(event)

        self._persist_planned_events(finalized)
        return finalized

    def run_forever(self) -> None:
        interval = float(self.auto_reply_config.get("poll_interval_seconds", 5))
        LOGGER.info(
            "Auto-reply daemon started. interval=%.2fs dry_run=%s",
            interval, self.dry_run_mode,
        )
        try:
            while True:
                self.run_once()
                self.sleep_func(interval)
        except KeyboardInterrupt:
            LOGGER.info("Auto-reply daemon stopped by Ctrl+C.")
        finally:
            self.state_store.close()
            self._status_watcher.close()


# ── CLI helpers ───────────────────────────────────────────────────────────────

def print_auto_reply_plan(config: dict[str, Any]) -> None:
    ar = auto_reply_config(config)
    owner_record = get_owner_status(config)
    owner = owner_config(config)
    unread = config.get("unread_scan", {}) if isinstance(config.get("unread_scan"), dict) else {}
    saved_status_allows_auto_reply = (
        owner_record.status == "online"
        and bool(ar.get("dry_run", True))
        and not bool(config.get("allow_real_send", False))
    )
    print("Auto-reply config:")
    for key in (
        "enabled", "dry_run", "delay_minutes", "poll_interval_seconds",
        "cooldown_minutes", "state_stale_minutes", "private_only",
        "require_private_chat_whitelist", "reply_message", "min_ocr_confidence",
    ):
        print(f"  {key}: {ar.get(key)}")
    print("Private chat whitelist:")
    whitelist = ar.get("private_chat_whitelist", [])
    if whitelist:
        for s in whitelist:
            print(f"  - {s}")
    else:
        print("  - none")
    print("Detection priority:")
    for source in ar.get("detection_priority", []):
        print(f"  - {source}")
    print("System status (macOS top-right corner):")
    print(f"  status: {owner_record.status}  (online=OL active, offline=OFF inactive)")
    updated = owner_record.updated_at.isoformat(timespec="seconds") if owner_record.updated_at else "none"
    print(f"  updated_at: {updated}")
    print(f"  source: {owner_record.source}")
    print(f"  immediate_reply_when_online: {owner.get('offline_reply_immediate', True)}")
    print("Safety status:")
    print(f"  dry_run: {ar.get('dry_run', True)}")
    print(f"  allow_real_send: {config.get('allow_real_send', False)}")
    print(f"  scroll_scan_default: {unread.get('enable_scroll_scan', False)}")
    print(f"  saved_status_allows_auto_reply: {saved_status_allows_auto_reply}")
    print("  live_status_check_required: True")
    print("  unknown_live_status_blocks: True")
    print(f"State storage: {config.get('database_path', 'data/wechat_assistant.sqlite3')}")
    print("What will be monitored:")
    print("  - macOS top-right corner (OL/OFF status) via screenshot OCR")
    print("  - macOS WeChat notification area via screenshot/OCR")
    print("  - WeChat left chat list unread indicators as fallback")
    print("What will be blocked:")
    for keyword in ar.get("blocklist_keywords", []):
        print(f"  - {keyword}")
    print("  - any sender matching (Name)(N) or (Name)（N人） group chat pattern")


def run_auto_reply_once(
    config: dict[str, Any],
    *,
    dry_run_mode: bool = True,
    notification_detector: Detector = detect_notification_events,
    unread_scanner: Detector = scan_unread_events,
    status_watcher: MacosStatusWatcher | None = None,
) -> list[AutoReplyEvent]:
    daemon = AutoReplyDaemon(
        config,
        dry_run_mode=dry_run_mode,
        notification_detector=notification_detector,
        unread_scanner=unread_scanner,
        status_watcher=status_watcher,
    )
    try:
        return daemon.run_once()
    finally:
        daemon.state_store.close()
        daemon._status_watcher.close()


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
