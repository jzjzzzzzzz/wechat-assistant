"""Limited-duration dry-run monitor for auto-reply soak testing."""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.auto_reply_daemon import AutoReplyDaemon
from src.auto_reply_policy import AutoReplyEvent, auto_reply_config, dry_run_action_text
from src.database import connect_database, initialize_database, resolve_database_path
from src.owner_status import get_owner_status
from src.unread_scanner import get_last_unread_scan_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MONITOR_LOG = "logs/auto_reply_monitor.log"
DEFAULT_EVENTS_JSONL = "logs/auto_reply_events.jsonl"


def _force_dry_run(config: dict[str, Any]) -> dict[str, Any]:
    copied = dict(config)
    ar = auto_reply_config(copied)
    ar["dry_run"] = True
    copied["auto_reply"] = ar
    copied["dry_run"] = True
    copied["allow_real_send"] = False
    return copied


def _project_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved


def _dt_text(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _event_to_dict(event: AutoReplyEvent) -> dict[str, Any]:
    elapsed = max(0.0, (event.last_seen_at - event.first_seen_at).total_seconds())
    return {
        "source": event.source,
        "sender": event.sender,
        "message_preview": event.message_preview,
        "detected_at": _dt_text(event.detected_at),
        "first_seen_at": _dt_text(event.first_seen_at),
        "last_seen_at": _dt_text(event.last_seen_at),
        "elapsed_seconds": elapsed,
        "confidence": round(float(event.confidence), 4),
        "status": event.status,
        "reason": event.reason,
        "is_private_candidate": event.is_private_candidate,
        "would_auto_reply": event.status == "ready_for_reply",
    }


def _scan_report_summary() -> dict[str, Any] | None:
    report = get_last_unread_scan_report()
    if report is None:
        return None
    paths = [
        path
        for path in (
            report.screenshot_path,
            report.chat_list_crop_path,
            report.red_mask_path,
            report.contour_overlay_path,
            report.row_overlay_path,
        )
        if path
    ]
    return {
        "screenshot_paths": paths,
        "contour_count": report.contour_count,
        "accepted_red_badge_count": report.accepted_badge_count,
        "rejected_red_contour_count": report.rejected_contour_count,
        "row_count": report.row_count,
        "association_count": report.association_count,
        "final_auto_reply_candidate_count": report.final_candidate_count,
        "ignored_reasons": list(report.ignored_reasons),
    }


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _setup_monitor_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("auto_reply_monitor")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    monitor_file_handler: logging.FileHandler | None = None
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path:
            monitor_file_handler = handler
            break
    if monitor_file_handler is None:
        monitor_file_handler = logging.FileHandler(log_path, encoding="utf-8")
        monitor_file_handler.setFormatter(formatter)
        logger.addHandler(monitor_file_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_has_monitor_file = any(
        isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path
        for handler in root_logger.handlers
    )
    if not root_has_monitor_file:
        root_logger.addHandler(monitor_file_handler)
    return logger


@dataclass(frozen=True)
class MonitorRunSummary:
    started_at: datetime
    completed_at: datetime
    duration_completed_seconds: float
    requested_minutes: float
    interval_seconds: float
    total_passes: int
    candidates_detected: int
    pending_count: int
    ready_for_reply_count: int
    ignored_count: int
    would_auto_reply_count: int
    ignored_reasons: dict[str, int]
    safe_failures: list[str]
    errors: list[str]
    monitor_log_path: str
    events_jsonl_path: str
    database_path: str
    stopped_by: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": _dt_text(self.started_at),
            "completed_at": _dt_text(self.completed_at),
            "duration_completed_seconds": round(self.duration_completed_seconds, 3),
            "requested_minutes": self.requested_minutes,
            "interval_seconds": self.interval_seconds,
            "total_passes": self.total_passes,
            "candidates_detected": self.candidates_detected,
            "pending_count": self.pending_count,
            "ready_for_reply_count": self.ready_for_reply_count,
            "ignored_count": self.ignored_count,
            "would_auto_reply_count": self.would_auto_reply_count,
            "ignored_reasons": self.ignored_reasons,
            "safe_failures": self.safe_failures,
            "errors": self.errors,
            "monitor_log_path": self.monitor_log_path,
            "events_jsonl_path": self.events_jsonl_path,
            "database_path": self.database_path,
            "stopped_by": self.stopped_by,
        }


class AutoReplyMonitor:
    """Run the dry-run daemon repeatedly for a bounded duration."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        interval_seconds: float,
        minutes: float,
        monitor_log_path: str | Path = DEFAULT_MONITOR_LOG,
        events_jsonl_path: str | Path = DEFAULT_EVENTS_JSONL,
        daemon_factory: Callable[[dict[str, Any]], Any] = AutoReplyDaemon,
        sleep_func: Callable[[float], None] = time.sleep,
        monotonic_func: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        if minutes < 0:
            raise ValueError("minutes must be >= 0")
        self.config = _force_dry_run(config)
        self.interval_seconds = float(interval_seconds)
        self.minutes = float(minutes)
        self.monitor_log_path = _project_path(monitor_log_path)
        self.events_jsonl_path = _project_path(events_jsonl_path)
        self.daemon_factory = daemon_factory
        self.sleep_func = sleep_func
        self.monotonic_func = monotonic_func
        self.logger = logger or _setup_monitor_logger(self.monitor_log_path)
        self.database_path = str(resolve_database_path(self.config.get("database_path")))

    def _record_run_summary(self, summary: MonitorRunSummary) -> None:
        try:
            database_path = initialize_database(self.config.get("database_path"))
            metadata = json.dumps(summary.as_dict(), ensure_ascii=False, sort_keys=True)
            with connect_database(database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO audit_events
                        (event_type, target, message_preview, safety_decision, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "auto_reply_monitor_summary",
                        "auto_reply_monitor",
                        f"passes={summary.total_passes} would={summary.would_auto_reply_count}",
                        "dry_run_no_send",
                        metadata,
                        summary.completed_at.isoformat(timespec="seconds"),
                    ),
                )
                connection.commit()
        except Exception as exc:
            self.logger.warning("Monitor summary SQLite write failed safely: %s", exc)

    def _pass_summary(self, pass_index: int, events: list[AutoReplyEvent], error: str | None = None) -> dict[str, Any]:
        owner_status = "unknown"
        owner_source = "unknown"
        try:
            owner = get_owner_status(self.config)
            owner_status = owner.status
            owner_source = owner.source
        except Exception as exc:
            error = error or f"owner status read failed: {exc}"

        statuses = Counter(event.status for event in events)
        reasons = Counter(event.reason for event in events if event.reason)
        scan_report = _scan_report_summary()
        safe_failures: list[str] = []
        if scan_report and not events and scan_report.get("ignored_reasons"):
            safe_failures.extend(str(reason) for reason in scan_report["ignored_reasons"])
        if error:
            safe_failures.append(error)

        payload = {
            "type": "monitor_pass",
            "pass_index": pass_index,
            "timestamp": _dt_text(datetime.now()),
            "owner_status": owner_status,
            "owner_status_source": owner_source,
            "detected_candidate_count": len(events),
            "pending_count": statuses.get("pending", 0),
            "ready_for_reply_count": statuses.get("ready_for_reply", 0),
            "ignored_count": statuses.get("ignored", 0),
            "ignored_reasons": dict(reasons),
            "would_auto_reply_count": statuses.get("ready_for_reply", 0),
            "events": [_event_to_dict(event) for event in events],
            "scan_report": scan_report,
            "safe_failures": safe_failures,
            "error": error,
            "dry_run": True,
            "allow_real_send": False,
        }
        return payload

    def run(self, *, max_passes: int | None = None) -> MonitorRunSummary:
        started_at = datetime.now()
        started_monotonic = self.monotonic_func()
        deadline = started_monotonic + self.minutes * 60.0
        total_events = 0
        pending_count = 0
        ready_count = 0
        ignored_count = 0
        would_count = 0
        reasons: Counter[str] = Counter()
        safe_failures: Counter[str] = Counter()
        errors: list[str] = []
        pass_index = 0
        stopped_by = "completed"
        daemon = self.daemon_factory(self.config)

        self.logger.info(
            "Auto-reply monitor starting dry_run=%s allow_real_send=%s interval=%.2fs minutes=%.2f",
            True,
            False,
            self.interval_seconds,
            self.minutes,
        )
        self.logger.info("Monitor JSONL events path: %s", self.events_jsonl_path)
        self.logger.info("Monitor SQLite database: %s", self.database_path)

        try:
            while True:
                if pass_index > 0 and self.monotonic_func() >= deadline:
                    break
                if max_passes is not None and pass_index >= max_passes:
                    break

                pass_index += 1
                self.logger.info("Monitor pass %s starting.", pass_index)
                events: list[AutoReplyEvent] = []
                error: str | None = None
                try:
                    events = list(daemon.run_once())
                except Exception as exc:
                    error = str(exc)
                    errors.append(error)
                    self.logger.exception("Monitor pass %s failed safely: %s", pass_index, exc)

                payload = self._pass_summary(pass_index, events, error=error)
                _append_jsonl(self.events_jsonl_path, payload)

                total_events += int(payload["detected_candidate_count"])
                pending_count += int(payload["pending_count"])
                ready_count += int(payload["ready_for_reply_count"])
                ignored_count += int(payload["ignored_count"])
                would_count += int(payload["would_auto_reply_count"])
                reasons.update(payload["ignored_reasons"])
                safe_failures.update(str(item) for item in payload["safe_failures"])

                self.logger.info(
                    "Monitor pass %s summary detected=%s pending=%s ready_for_reply=%s ignored=%s would=%s reasons=%s",
                    pass_index,
                    payload["detected_candidate_count"],
                    payload["pending_count"],
                    payload["ready_for_reply_count"],
                    payload["ignored_count"],
                    payload["would_auto_reply_count"],
                    payload["ignored_reasons"],
                )
                for event in events:
                    if event.status == "ready_for_reply":
                        self.logger.info(dry_run_action_text(event, self.config).replace("\n", " | "))

                if max_passes is not None and pass_index >= max_passes:
                    break
                remaining = deadline - self.monotonic_func()
                if remaining <= 0:
                    break
                self.sleep_func(min(self.interval_seconds, remaining))
        except KeyboardInterrupt:
            stopped_by = "keyboard_interrupt"
            self.logger.info("Auto-reply monitor stopped by Ctrl+C.")
        finally:
            state_store = getattr(daemon, "state_store", None)
            if state_store is not None:
                try:
                    state_store.close()
                except Exception:
                    pass

        completed_at = datetime.now()
        summary = MonitorRunSummary(
            started_at=started_at,
            completed_at=completed_at,
            duration_completed_seconds=max(0.0, self.monotonic_func() - started_monotonic),
            requested_minutes=self.minutes,
            interval_seconds=self.interval_seconds,
            total_passes=pass_index,
            candidates_detected=total_events,
            pending_count=pending_count,
            ready_for_reply_count=ready_count,
            ignored_count=ignored_count,
            would_auto_reply_count=would_count,
            ignored_reasons=dict(reasons),
            safe_failures=list(safe_failures.keys()),
            errors=errors,
            monitor_log_path=str(self.monitor_log_path),
            events_jsonl_path=str(self.events_jsonl_path),
            database_path=self.database_path,
            stopped_by=stopped_by,
        )
        self._record_run_summary(summary)
        self.logger.info("Auto-reply monitor completed: %s", summary.as_dict())
        return summary


def run_auto_reply_monitor(
    config: dict[str, Any],
    *,
    interval_seconds: float | None = None,
    minutes: float = 60.0,
) -> MonitorRunSummary:
    ar = auto_reply_config(config)
    interval = float(interval_seconds if interval_seconds is not None else ar.get("poll_interval_seconds", 5))
    monitor = AutoReplyMonitor(config, interval_seconds=interval, minutes=float(minutes))
    return monitor.run()


def print_monitor_summary(summary: MonitorRunSummary) -> None:
    data = summary.as_dict()
    for key in (
        "started_at",
        "completed_at",
        "duration_completed_seconds",
        "requested_minutes",
        "interval_seconds",
        "total_passes",
        "candidates_detected",
        "pending_count",
        "ready_for_reply_count",
        "ignored_count",
        "would_auto_reply_count",
        "ignored_reasons",
        "safe_failures",
        "errors",
        "monitor_log_path",
        "events_jsonl_path",
        "database_path",
        "stopped_by",
    ):
        print(f"{key}: {data[key]}")


def print_monitor_report(config: dict[str, Any], *, limit: int = 3) -> int:
    database_path = initialize_database(config.get("database_path"))
    print(f"database_path: {database_path}")
    with connect_database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT created_at, metadata_json
            FROM audit_events
            WHERE event_type = 'auto_reply_monitor_summary'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    if not rows:
        print("No auto-reply monitor summaries found.")
        return 0

    for index, row in enumerate(rows, start=1):
        try:
            metadata = json.loads(str(row["metadata_json"]))
        except Exception:
            metadata = {"raw": row["metadata_json"]}
        print(f"summary[{index}].created_at: {row['created_at']}")
        for key in (
            "duration_completed_seconds",
            "total_passes",
            "candidates_detected",
            "pending_count",
            "ready_for_reply_count",
            "ignored_count",
            "would_auto_reply_count",
            "ignored_reasons",
            "safe_failures",
            "errors",
            "monitor_log_path",
            "events_jsonl_path",
            "stopped_by",
        ):
            print(f"summary[{index}].{key}: {metadata.get(key)}")
    return 0
