import plistlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict:
    text = (PROJECT_ROOT / "launchd" / name).read_text(encoding="utf-8")
    text = text.replace("__PROJECT_DIR__", "/tmp/wechat-assistant")
    return plistlib.loads(text.encode("utf-8"))


def test_status_menu_launchagent_runs_only_status_menu():
    data = _load_template("com.wechat-assistant.status-menu.plist.template")

    assert data["Label"] == "com.wechat-assistant.status-menu"
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"] is True
    assert data["ProgramArguments"] == [
        "/tmp/wechat-assistant/.venv/bin/python",
        "-u",
        "-m",
        "src.main",
        "status-menu",
    ]
    assert "auto-reply" not in " ".join(data["ProgramArguments"])


def test_auto_reply_daemon_launchagent_is_dry_run_only():
    data = _load_template("com.wechat-assistant.auto-reply-daemon.plist.template")
    args = data["ProgramArguments"]

    assert data["Label"] == "com.wechat-assistant.auto-reply-daemon"
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"] is True
    assert args == [
        "/tmp/wechat-assistant/.venv/bin/python",
        "-u",
        "-m",
        "src.main",
        "auto-reply-daemon",
        "--dry-run",
    ]
    assert "--force-send" not in args
    assert "--dry-run" in args


def test_install_runtime_launchagents_refuses_unsafe_config():
    text = (PROJECT_ROOT / "scripts" / "install_runtime_launchagents.sh").read_text(encoding="utf-8")

    assert "Refusing to install runtime LaunchAgents" in text
    assert "dry_run: true" in text
    assert "auto_reply.dry_run: true" in text
    assert "allow_real_send: false" in text
    assert "auto-reply-daemon" in text
    assert "--dry-run" in text


def test_uninstall_runtime_launchagents_removes_only_runtime_labels():
    text = (PROJECT_ROOT / "scripts" / "uninstall_runtime_launchagents.sh").read_text(encoding="utf-8")

    assert "com.wechat-assistant.status-menu" in text
    assert "com.wechat-assistant.auto-reply-daemon" in text
    assert "bootout" in text
    assert "birthday" not in text
