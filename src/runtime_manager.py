"""Runtime process helpers for safe local launch scripts.

These helpers manage only this project's menu and dry-run monitor commands.
They do not scan WeChat, run OCR, send messages, or control the WeChat UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import signal
import subprocess
import time
from typing import Any

from src.auto_reply_policy import auto_reply_config
from src.owner_status import get_owner_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimeProcessSpec:
    name: str
    pid_file: Path
    log_file: Path
    process_marker: str


@dataclass(frozen=True)
class RuntimeProcessStatus:
    name: str
    pid: int | None
    running: bool
    source: str
    pid_file: Path
    log_file: Path
    command: str = ""
    note: str = ""


@dataclass(frozen=True)
class StopResult:
    name: str
    pid: int | None
    stopped: bool
    pid_file_removed: bool
    message: str


STATUS_MENU_SPEC = RuntimeProcessSpec(
    name="status-menu",
    pid_file=PROJECT_ROOT / "run" / "status_menu.pid",
    log_file=PROJECT_ROOT / "logs" / "status_menu.log",
    process_marker="src.main status-menu",
)
STATUS_WINDOW_SPEC = RuntimeProcessSpec(
    name="status-window",
    pid_file=PROJECT_ROOT / "run" / "status_window.pid",
    log_file=PROJECT_ROOT / "logs" / "status_window.log",
    process_marker="src.main status-window",
)
MONITOR_SPEC = RuntimeProcessSpec(
    name="auto-reply-monitor",
    pid_file=PROJECT_ROOT / "run" / "auto_reply_monitor.pid",
    log_file=PROJECT_ROOT / "logs" / "auto_reply_monitor.log",
    process_marker="src.main auto-reply-monitor",
)

STATUS_MENU_LAUNCHAGENT_LABEL = "com.wechat-assistant.status-menu"
STATUS_WINDOW_LAUNCHAGENT_LABEL = "com.wechat-assistant.status-window"
AUTO_REPLY_DAEMON_LAUNCHAGENT_LABEL = "com.wechat-assistant.auto-reply-daemon"
STATUS_MENU_LAUNCHAGENT_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{STATUS_MENU_LAUNCHAGENT_LABEL}.plist"
STATUS_WINDOW_LAUNCHAGENT_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{STATUS_WINDOW_LAUNCHAGENT_LABEL}.plist"
AUTO_REPLY_DAEMON_LAUNCHAGENT_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / f"{AUTO_REPLY_DAEMON_LAUNCHAGENT_LABEL}.plist"
)
STATUS_MENU_LAUNCHAGENT_LOG = PROJECT_ROOT / "logs" / "status_menu_launchagent.log"
STATUS_WINDOW_LAUNCHAGENT_LOG = PROJECT_ROOT / "logs" / "status_window_launchagent.log"
AUTO_REPLY_DAEMON_LAUNCHAGENT_LOG = PROJECT_ROOT / "logs" / "auto_reply_daemon_launchagent.log"


def read_pid_file(path: str | Path) -> int | None:
    pid_path = Path(path)
    try:
        text = pid_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    if not text:
        return None
    try:
        pid = int(text)
    except ValueError:
        return None
    return pid if pid > 0 else None


def remove_pid_file(path: str | Path) -> bool:
    try:
        Path(path).unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_command(pid: int) -> str:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _find_pids_by_marker(marker: str) -> list[tuple[int, str]]:
    try:
        result = subprocess.run(
            ["pgrep", "-f", marker],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []

    matches: list[tuple[int, str]] = []
    current_pid = os.getpid()
    parent_pid = os.getppid()
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid in {current_pid, parent_pid}:
            continue
        command = _process_command(pid)
        if marker in command and "pgrep" not in command:
            matches.append((pid, command))
    return matches


def inspect_runtime_process(
    spec: RuntimeProcessSpec,
    *,
    scan_processes: bool = True,
) -> RuntimeProcessStatus:
    pid = read_pid_file(spec.pid_file)
    if pid is not None:
        command = _process_command(pid)
        if _is_pid_running(pid) and spec.process_marker in command:
            return RuntimeProcessStatus(
                spec.name,
                pid,
                True,
                "pid_file",
                spec.pid_file,
                spec.log_file,
                command=command,
            )
        if _is_pid_running(pid):
            return RuntimeProcessStatus(
                spec.name,
                pid,
                False,
                "stale_pid_file",
                spec.pid_file,
                spec.log_file,
                command=command,
                note="pid is running but does not match this project command",
            )
        return RuntimeProcessStatus(
            spec.name,
            pid,
            False,
            "stale_pid_file",
            spec.pid_file,
            spec.log_file,
            note="pid file exists but process is not running",
        )

    if scan_processes:
        matches = _find_pids_by_marker(spec.process_marker)
        if matches:
            found_pid, command = matches[0]
            return RuntimeProcessStatus(
                spec.name,
                found_pid,
                True,
                "process_scan",
                spec.pid_file,
                spec.log_file,
                command=command,
                note="running process found without pid file",
            )

    return RuntimeProcessStatus(spec.name, None, False, "none", spec.pid_file, spec.log_file)


def stop_runtime_process(
    spec: RuntimeProcessSpec,
    *,
    timeout_seconds: float = 5.0,
    scan_processes: bool = True,
) -> StopResult:
    status = inspect_runtime_process(spec, scan_processes=scan_processes)
    removed = False
    if not status.running:
        if status.source == "stale_pid_file":
            removed = remove_pid_file(spec.pid_file)
            return StopResult(
                spec.name,
                status.pid,
                False,
                removed,
                f"{spec.name}: removed stale pid file",
            )
        return StopResult(spec.name, status.pid, False, False, f"{spec.name}: not running")

    if status.pid is None:
        return StopResult(spec.name, None, False, False, f"{spec.name}: no pid to stop")

    if spec.process_marker not in status.command:
        return StopResult(
            spec.name,
            status.pid,
            False,
            False,
            f"{spec.name}: refused to stop pid because command does not match",
        )

    try:
        os.kill(status.pid, signal.SIGTERM)
    except ProcessLookupError:
        removed = remove_pid_file(spec.pid_file)
        return StopResult(spec.name, status.pid, False, removed, f"{spec.name}: process already stopped")
    except PermissionError:
        return StopResult(spec.name, status.pid, False, False, f"{spec.name}: permission denied stopping process")

    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        if not _is_pid_running(status.pid):
            removed = remove_pid_file(spec.pid_file)
            return StopResult(spec.name, status.pid, True, removed, f"{spec.name}: stopped")
        time.sleep(0.1)

    return StopResult(spec.name, status.pid, False, False, f"{spec.name}: stop timed out")


def runtime_process_statuses() -> list[RuntimeProcessStatus]:
    return [
        inspect_runtime_process(STATUS_MENU_SPEC),
        inspect_runtime_process(STATUS_WINDOW_SPEC),
        inspect_runtime_process(MONITOR_SPEC),
    ]


def _path_text(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = PROJECT_ROOT / value
    return str(value)


def format_runtime_status(config: dict[str, Any]) -> str:
    owner = get_owner_status(config)
    ar = auto_reply_config(config)
    lines = [
        "Runtime status:",
        "Owner:",
        f"  status: {owner.status}",
        f"  updated_at: {owner.updated_at.isoformat(timespec='seconds') if owner.updated_at else 'none'}",
        f"  source: {owner.source}",
        "Safety:",
        f"  dry_run: {bool(config.get('dry_run', True))}",
        f"  auto_reply.dry_run: {bool(ar.get('dry_run', True))}",
        f"  allow_real_send: {bool(config.get('allow_real_send', False))}",
        "Processes:",
    ]

    for status in runtime_process_statuses():
        pid_text = str(status.pid) if status.pid is not None else "none"
        state = "running" if status.running else "stopped"
        lines.append(f"  {status.name}: {state}")
        lines.append(f"    pid: {pid_text}")
        lines.append(f"    source: {status.source}")
        if status.note:
            lines.append(f"    note: {status.note}")
        lines.append(f"    pid_file: {status.pid_file}")
        lines.append(f"    log_file: {status.log_file}")

    lines.extend(
        [
            "LaunchAgents:",
            f"  {STATUS_MENU_LAUNCHAGENT_LABEL}: {STATUS_MENU_LAUNCHAGENT_PLIST}",
            f"    log_file: {STATUS_MENU_LAUNCHAGENT_LOG}",
            f"  {STATUS_WINDOW_LAUNCHAGENT_LABEL}: {STATUS_WINDOW_LAUNCHAGENT_PLIST}",
            f"    log_file: {STATUS_WINDOW_LAUNCHAGENT_LOG}",
            f"  {AUTO_REPLY_DAEMON_LAUNCHAGENT_LABEL}: {AUTO_REPLY_DAEMON_LAUNCHAGENT_PLIST}",
            f"    log_file: {AUTO_REPLY_DAEMON_LAUNCHAGENT_LOG}",
        ]
    )

    lines.extend(
        [
            "Paths:",
            f"  app_log: {_path_text(config.get('log_file', 'logs/app.log'))}",
            f"  status_menu_log: {STATUS_MENU_SPEC.log_file}",
            f"  status_window_log: {STATUS_WINDOW_SPEC.log_file}",
            f"  monitor_log: {MONITOR_SPEC.log_file}",
            f"  monitor_events_jsonl: {PROJECT_ROOT / 'logs' / 'auto_reply_events.jsonl'}",
            f"  database_path: {_path_text(config.get('database_path', 'data/wechat_assistant.sqlite3'))}",
        ]
    )
    return "\n".join(lines)


def print_runtime_status(config: dict[str, Any]) -> None:
    print(format_runtime_status(config))


def stop_all_runtime_processes() -> list[StopResult]:
    return [
        stop_runtime_process(STATUS_MENU_SPEC),
        stop_runtime_process(STATUS_WINDOW_SPEC),
        stop_runtime_process(MONITOR_SPEC),
    ]


def print_stop_all_results() -> int:
    results = stop_all_runtime_processes()
    for result in results:
        pid_text = str(result.pid) if result.pid is not None else "none"
        print(
            f"{result.name}: stopped={result.stopped} pid={pid_text} "
            f"pid_file_removed={result.pid_file_removed} message={result.message}"
        )
    ok = all(
        result.stopped or "not running" in result.message or "stale" in result.message
        for result in results
    )
    return 0 if ok else 1
