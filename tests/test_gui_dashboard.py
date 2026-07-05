from pathlib import Path
from types import SimpleNamespace

from src.gui.dashboard import DashboardCommandRunner, dashboard_status_from_config


def test_dashboard_status_from_config_maps_safety_fields() -> None:
    status = dashboard_status_from_config(
        {
            "dry_run": True,
            "allow_real_send": False,
            "test_contact": "文件传输助手",
            "log_file": "logs/app.log",
        }
    )

    assert status.dry_run is True
    assert status.allow_real_send is False
    assert status.test_contact == "文件传输助手"
    assert "DRY RUN ON" in status.safety_summary


def test_dashboard_runner_dispatches_check_callback() -> None:
    runner = DashboardCommandRunner(
        {},
        check_func=lambda: [SimpleNamespace(ok=True), SimpleNamespace(ok=True)],
    )

    assert runner.run_check() == "Environment check passed"


def test_dashboard_runner_dispatches_screenshot_callback() -> None:
    runner = DashboardCommandRunner(
        {"dry_run": True},
        screenshot_func=lambda config: "/tmp/screen.png",
    )

    assert runner.run_screenshot() == "Screenshot saved: /tmp/screen.png"


def test_dashboard_runner_dispatches_test_send_callback() -> None:
    runner = DashboardCommandRunner(
        {"dry_run": True},
        test_send_func=lambda config: True,
    )

    assert runner.run_test_send() == "Test send dry-run completed"


def test_dashboard_runner_open_logs_uses_open_callback(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    log_path = tmp_path / "app.log"
    runner = DashboardCommandRunner(
        {"log_file": str(log_path)},
        open_func=lambda args: calls.append(args),
    )

    message = runner.open_logs()

    assert calls == [["open", str(log_path)]]
    assert log_path.exists()
    assert message == f"Opened log file: {log_path}"
