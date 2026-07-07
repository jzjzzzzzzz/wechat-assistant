#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${WECHAT_ASSISTANT_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
CONFIG_PATH="${WECHAT_ASSISTANT_CONFIG_PATH:-$PROJECT_DIR/config/settings.yaml}"
LAUNCHAGENTS_DIR="${WECHAT_ASSISTANT_LAUNCHAGENTS_DIR:-$HOME/Library/LaunchAgents}"
DOMAIN="${WECHAT_ASSISTANT_LAUNCHCTL_DOMAIN:-gui/$UID}"

STATUS_LABEL="com.wechat-assistant.status-menu"
STATUS_WINDOW_LABEL="com.wechat-assistant.status-window"
DAEMON_LABEL="com.wechat-assistant.auto-reply-daemon"
STATUS_TEMPLATE="$PROJECT_DIR/launchd/$STATUS_LABEL.plist.template"
STATUS_WINDOW_TEMPLATE="$PROJECT_DIR/launchd/$STATUS_WINDOW_LABEL.plist.template"
DAEMON_TEMPLATE="$PROJECT_DIR/launchd/$DAEMON_LABEL.plist.template"
STATUS_TARGET="$LAUNCHAGENTS_DIR/$STATUS_LABEL.plist"
STATUS_WINDOW_TARGET="$LAUNCHAGENTS_DIR/$STATUS_WINDOW_LABEL.plist"
DAEMON_TARGET="$LAUNCHAGENTS_DIR/$DAEMON_LABEL.plist"

if [[ -n "${WECHAT_ASSISTANT_PYTHON:-}" ]]; then
    PYTHON="$WECHAT_ASSISTANT_PYTHON"
else
    if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
        echo "Missing virtualenv python: $PROJECT_DIR/.venv/bin/python"
        exit 1
    fi
    PYTHON="$PROJECT_DIR/.venv/bin/python"
fi

"$PYTHON" - "$CONFIG_PATH" <<'PY'
from pathlib import Path
import sys
import yaml

config_path = Path(sys.argv[1])
config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
auto_reply = config.get("auto_reply", {}) if isinstance(config.get("auto_reply"), dict) else {}
root_dry_run = config.get("dry_run") is True
auto_reply_dry_run = auto_reply.get("dry_run", True) is True
real_send_disabled = config.get("allow_real_send") is False
if not root_dry_run or not auto_reply_dry_run or not real_send_disabled:
    print("Refusing to install runtime LaunchAgents: requires dry_run: true, auto_reply.dry_run: true, allow_real_send: false.")
    print(f"config: {config_path}")
    sys.exit(2)
PY

mkdir -p "$LAUNCHAGENTS_DIR" "$PROJECT_DIR/logs"

render_template() {
    local template="$1"
    local target="$2"
    "$PYTHON" - "$template" "$target" "$PROJECT_DIR" <<'PY'
from pathlib import Path
import sys

template = Path(sys.argv[1])
target = Path(sys.argv[2])
project_dir = sys.argv[3]
text = template.read_text(encoding="utf-8").replace("__PROJECT_DIR__", project_dir)
target.write_text(text, encoding="utf-8")
PY
}

install_agent() {
    local label="$1"
    local template="$2"
    local target="$3"

    render_template "$template" "$target"
    launchctl bootout "$DOMAIN" "$target" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$target"
    launchctl enable "$DOMAIN/$label" 2>/dev/null || true
    launchctl kickstart -k "$DOMAIN/$label"
    echo "Installed LaunchAgent: $target"
    echo "Label: $label"
}

install_agent "$STATUS_LABEL" "$STATUS_TEMPLATE" "$STATUS_TARGET"
install_agent "$STATUS_WINDOW_LABEL" "$STATUS_WINDOW_TEMPLATE" "$STATUS_WINDOW_TARGET"
install_agent "$DAEMON_LABEL" "$DAEMON_TEMPLATE" "$DAEMON_TARGET"

echo "Runtime LaunchAgents installed."
echo "status-menu log: $PROJECT_DIR/logs/status_menu_launchagent.log"
echo "status-window log: $PROJECT_DIR/logs/status_window_launchagent.log"
echo "auto-reply daemon log: $PROJECT_DIR/logs/auto_reply_daemon_launchagent.log"
echo "Safety: auto-reply daemon is installed with --dry-run."
