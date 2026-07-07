"""Real-send drain loop for offline unread auto-replies.

The drain command is intentionally explicit: it only runs in real-send mode
when root dry_run is false, auto_reply.dry_run is false, and allow_real_send is
true.  It enables chat-list scroll scanning for the run, executes normal daemon
passes, and stops when the WeChat Dock unread badge disappears or max_passes is
reached.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from src.auto_reply_daemon import AutoReplyDaemon
from src.auto_reply_policy import AutoReplyEvent
from src.dock_unread_detector import DockUnreadDetection, detect_dock_wechat_unread, dock_unread_config
from src.wechat_window import activate_wechat_result


LOGGER = logging.getLogger(__name__)
DaemonFactory = Callable[..., Any]
DockDetector = Callable[[dict[str, Any]], DockUnreadDetection]
ActivateFunc = Callable[..., Any]


@dataclass(frozen=True)
class AutoReplyDrainSummary:
    started_at: datetime
    completed_at: datetime
    total_passes: int
    max_passes: int
    interval_seconds: float
    detected_candidate_count: int
    ready_for_reply_count: int
    ignored_count: int
    pending_count: int
    real_send_candidate_count: int
    stopped_by: str
    final_dock_has_unread: bool | None
    errors: tuple[str, ...] = ()


def _real_send_mode(config: dict[str, Any]) -> bool:
    ar = config.get("auto_reply", {}) if isinstance(config.get("auto_reply"), dict) else {}
    return (
        not bool(config.get("dry_run", True))
        and not bool(ar.get("dry_run", True))
        and bool(config.get("allow_real_send", False))
    )


def _enable_drain_scan(config: dict[str, Any]) -> dict[str, Any]:
    copied = dict(config)
    unread = dict(copied.get("unread_scan", {}))
    unread["enable_scroll_scan"] = True
    unread["ensure_wechat_frontmost_for_scroll"] = True
    unread["restore_position_after_scan"] = True
    unread["stop_on_first_private_candidate"] = False
    copied["unread_scan"] = unread
    return copied


def _dock_enabled_for_drain(config: dict[str, Any]) -> bool:
    dock = dock_unread_config(config)
    return bool(dock.get("enabled", False)) and bool(dock.get("require_for_auto_reply", False))


def _safe_dock_detect(detector: DockDetector, config: dict[str, Any], errors: list[str]) -> DockUnreadDetection | None:
    try:
        detection = detector(config)
        LOGGER.info(
            "Drain Dock check: ok=%s has_unread=%s confidence=%.3f message=%s",
            detection.ok,
            detection.has_unread,
            detection.confidence,
            detection.message,
        )
        return detection
    except Exception as exc:
        message = f"dock detection failed: {exc}"
        LOGGER.warning("Drain %s", message)
        errors.append(message)
        return None


def _activate_wechat_for_drain(config: dict[str, Any], activate_func: ActivateFunc, errors: list[str]) -> None:
    app_name = str(config.get("wechat_app_name", "WeChat"))
    try:
        result = activate_func(app_name, wait_seconds=1.0, retry_count=2)
        if hasattr(result, "ok") and not result.ok:
            message = f"WeChat activation failed before drain scan: {getattr(result, 'message', result)}"
            LOGGER.warning("Drain %s", message)
            errors.append(message)
        elif result is False:
            message = "WeChat activation failed before drain scan"
            LOGGER.warning("Drain %s", message)
            errors.append(message)
        else:
            LOGGER.info("Drain WeChat foreground check completed before scan.")
    except Exception as exc:
        message = f"WeChat activation raised before drain scan: {exc}"
        LOGGER.warning("Drain %s", message)
        errors.append(message)


def run_auto_reply_drain(
    config: dict[str, Any],
    *,
    max_passes: int = 10,
    interval_seconds: float = 2.0,
    daemon_factory: DaemonFactory = AutoReplyDaemon,
    dock_unread_detector: DockDetector = detect_dock_wechat_unread,
    activate_func: ActivateFunc = activate_wechat_result,
    sleep_func: Callable[[float], None] = time.sleep,
) -> AutoReplyDrainSummary:
    if max_passes <= 0:
        raise ValueError("max_passes must be > 0")
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be >= 0")
    if not _real_send_mode(config):
        raise ValueError("auto-reply-drain requires real-send mode; run with --force-send or real config flags")
    if not _dock_enabled_for_drain(config):
        raise ValueError("auto-reply-drain requires dock_unread.enabled=true and require_for_auto_reply=true")

    drain_config = _enable_drain_scan(config)
    started_at = datetime.now()
    detected_total = 0
    ready_total = 0
    ignored_total = 0
    pending_total = 0
    real_send_candidates = 0
    errors: list[str] = []
    final_dock: bool | None = None
    stopped_by = "max_passes"
    pass_count = 0

    LOGGER.warning(
        "Auto-reply drain starting. real_send=True scroll_scan=True max_passes=%s interval=%.2fs",
        max_passes,
        interval_seconds,
    )

    daemon = daemon_factory(drain_config, dry_run_mode=False)
    try:
        for pass_index in range(1, max_passes + 1):
            before = _safe_dock_detect(dock_unread_detector, drain_config, errors)
            final_dock = before.safe_gate_value if before else None
            if before is None or before.safe_gate_value is not True:
                stopped_by = "dock_unread_cleared" if before and before.has_unread is False else "dock_unread_not_confirmed"
                break

            pass_count = pass_index
            _activate_wechat_for_drain(drain_config, activate_func, errors)
            LOGGER.info("Drain pass %s starting.", pass_index)
            events: list[AutoReplyEvent] = []
            try:
                events = list(daemon.run_once())
            except Exception as exc:
                message = f"daemon pass {pass_index} failed: {exc}"
                LOGGER.exception("Drain %s", message)
                errors.append(message)

            statuses = Counter(event.status for event in events)
            detected_total += len(events)
            ready_total += statuses.get("ready_for_reply", 0)
            ignored_total += statuses.get("ignored", 0)
            pending_total += statuses.get("pending", 0)
            real_send_candidates += statuses.get("ready_for_reply", 0)
            LOGGER.info(
                "Drain pass %s summary detected=%s pending=%s ready=%s ignored=%s",
                pass_index,
                len(events),
                statuses.get("pending", 0),
                statuses.get("ready_for_reply", 0),
                statuses.get("ignored", 0),
            )

            after = _safe_dock_detect(dock_unread_detector, drain_config, errors)
            final_dock = after.safe_gate_value if after else None
            if after and after.has_unread is False:
                stopped_by = "dock_unread_cleared"
                break
            if interval_seconds and pass_index < max_passes:
                sleep_func(interval_seconds)
    finally:
        state_store = getattr(daemon, "state_store", None)
        if state_store is not None:
            state_store.close()
        status_watcher = getattr(daemon, "_status_watcher", None)
        if status_watcher is not None:
            status_watcher.close()

    completed_at = datetime.now()
    return AutoReplyDrainSummary(
        started_at=started_at,
        completed_at=completed_at,
        total_passes=pass_count,
        max_passes=max_passes,
        interval_seconds=interval_seconds,
        detected_candidate_count=detected_total,
        ready_for_reply_count=ready_total,
        ignored_count=ignored_total,
        pending_count=pending_total,
        real_send_candidate_count=real_send_candidates,
        stopped_by=stopped_by,
        final_dock_has_unread=final_dock,
        errors=tuple(errors),
    )


def print_drain_summary(summary: AutoReplyDrainSummary) -> None:
    print("Auto-reply drain summary:")
    print(f"  started_at: {summary.started_at.isoformat(timespec='seconds')}")
    print(f"  completed_at: {summary.completed_at.isoformat(timespec='seconds')}")
    print(f"  total_passes: {summary.total_passes}")
    print(f"  max_passes: {summary.max_passes}")
    print(f"  stopped_by: {summary.stopped_by}")
    print(f"  final_dock_has_unread: {summary.final_dock_has_unread}")
    print(f"  detected_candidate_count: {summary.detected_candidate_count}")
    print(f"  pending_count: {summary.pending_count}")
    print(f"  ready_for_reply_count: {summary.ready_for_reply_count}")
    print(f"  ignored_count: {summary.ignored_count}")
    print(f"  real_send_candidate_count: {summary.real_send_candidate_count}")
    if summary.errors:
        print("  errors:")
        for error in summary.errors:
            print(f"    - {error}")
