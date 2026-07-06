import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_start_monitor_script_refuses_unsafe_config(tmp_path):
    unsafe_config = tmp_path / "settings.yaml"
    unsafe_config.write_text(
        "\n".join(
            [
                "dry_run: false",
                "allow_real_send: true",
                "auto_reply:",
                "  dry_run: false",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["WECHAT_ASSISTANT_CONFIG_PATH"] = str(unsafe_config)
    env["WECHAT_ASSISTANT_PROJECT_DIR"] = str(PROJECT_ROOT)
    env["WECHAT_ASSISTANT_PYTHON"] = sys.executable
    result = subprocess.run(
        ["bash", str(PROJECT_ROOT / "scripts" / "start_monitor.sh")],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert "Refusing to start monitor" in result.stdout


def test_stop_status_menu_script_handles_stale_pid(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    pid_file = run_dir / "status_menu.pid"
    pid_file.write_text("999999\n", encoding="utf-8")

    env = os.environ.copy()
    env["WECHAT_ASSISTANT_PROJECT_DIR"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(PROJECT_ROOT / "scripts" / "stop_status_menu.sh")],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "stale" in result.stdout
    assert not pid_file.exists()


def test_stop_monitor_script_handles_stale_pid(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    pid_file = run_dir / "auto_reply_monitor.pid"
    pid_file.write_text("999999\n", encoding="utf-8")

    env = os.environ.copy()
    env["WECHAT_ASSISTANT_PROJECT_DIR"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(PROJECT_ROOT / "scripts" / "stop_monitor.sh")],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "stale" in result.stdout
    assert not pid_file.exists()
