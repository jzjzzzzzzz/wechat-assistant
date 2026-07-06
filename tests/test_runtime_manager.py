from datetime import datetime
from pathlib import Path

import src.runtime_manager as runtime_manager
from src.owner_status import OwnerStatusRecord


BASE_TIME = datetime(2026, 7, 6, 12, 0, 0)


def test_pid_file_handling_reports_stale_pid(tmp_path, monkeypatch):
    pid_file = tmp_path / "status_menu.pid"
    log_file = tmp_path / "status_menu.log"
    pid_file.write_text("999999\n", encoding="utf-8")
    spec = runtime_manager.RuntimeProcessSpec(
        name="status-menu",
        pid_file=pid_file,
        log_file=log_file,
        process_marker="src.main status-menu",
    )
    monkeypatch.setattr(runtime_manager, "_is_pid_running", lambda pid: False)
    monkeypatch.setattr(runtime_manager, "_process_command", lambda pid: "")

    status = runtime_manager.inspect_runtime_process(spec, scan_processes=False)

    assert status.running is False
    assert status.pid == 999999
    assert status.source == "stale_pid_file"
    assert "not running" in status.note


def test_stop_runtime_process_removes_stale_pid_file(tmp_path, monkeypatch):
    pid_file = tmp_path / "status_menu.pid"
    log_file = tmp_path / "status_menu.log"
    pid_file.write_text("999999\n", encoding="utf-8")
    spec = runtime_manager.RuntimeProcessSpec(
        name="status-menu",
        pid_file=pid_file,
        log_file=log_file,
        process_marker="src.main status-menu",
    )
    monkeypatch.setattr(runtime_manager, "_is_pid_running", lambda pid: False)
    monkeypatch.setattr(runtime_manager, "_process_command", lambda pid: "")

    result = runtime_manager.stop_runtime_process(spec, scan_processes=False)

    assert result.stopped is False
    assert result.pid_file_removed is True
    assert not pid_file.exists()
    assert "stale" in result.message


def test_runtime_status_formatting_includes_safety_and_paths(monkeypatch, tmp_path):
    config = {
        "dry_run": True,
        "allow_real_send": False,
        "log_file": "logs/app.log",
        "database_path": str(tmp_path / "wechat_assistant.sqlite3"),
        "auto_reply": {"dry_run": True},
        "owner": {"status_default": "online"},
    }
    monkeypatch.setattr(
        runtime_manager,
        "get_owner_status",
        lambda cfg: OwnerStatusRecord("online", BASE_TIME, "test", None, "database"),
    )
    monkeypatch.setattr(
        runtime_manager,
        "runtime_process_statuses",
        lambda: [
            runtime_manager.RuntimeProcessStatus(
                "status-menu",
                123,
                True,
                "pid_file",
                Path("run/status_menu.pid"),
                Path("logs/status_menu.log"),
            ),
            runtime_manager.RuntimeProcessStatus(
                "auto-reply-monitor",
                None,
                False,
                "none",
                Path("run/auto_reply_monitor.pid"),
                Path("logs/auto_reply_monitor.log"),
            ),
        ],
    )

    output = runtime_manager.format_runtime_status(config)

    assert "Runtime status:" in output
    assert "status: online" in output
    assert "dry_run: True" in output
    assert "auto_reply.dry_run: True" in output
    assert "allow_real_send: False" in output
    assert "status-menu: running" in output
    assert "auto-reply-monitor: stopped" in output
    assert "database_path:" in output


def test_dry_run_remains_default_in_runtime_status_config():
    config = {
        "dry_run": True,
        "allow_real_send": False,
        "auto_reply": {"dry_run": True},
    }

    ar = runtime_manager.auto_reply_config(config)

    assert config["dry_run"] is True
    assert config["allow_real_send"] is False
    assert ar["dry_run"] is True
