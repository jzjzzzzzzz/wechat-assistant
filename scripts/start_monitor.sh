#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${WECHAT_ASSISTANT_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
CONFIG_PATH="${WECHAT_ASSISTANT_CONFIG_PATH:-$PROJECT_DIR/config/settings.yaml}"
PID_FILE="$PROJECT_DIR/run/auto_reply_monitor.pid"
LOG_FILE="$PROJECT_DIR/logs/auto_reply_monitor.log"
MARKER="src.main auto-reply-monitor"

mkdir -p "$PROJECT_DIR/run" "$PROJECT_DIR/logs"

if [[ -n "${WECHAT_ASSISTANT_PYTHON:-}" ]]; then
    PYTHON="$WECHAT_ASSISTANT_PYTHON"
else
    if [[ ! -f "$PROJECT_DIR/.venv/bin/activate" ]]; then
        echo "Missing virtualenv: $PROJECT_DIR/.venv"
        exit 1
    fi
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.venv/bin/activate"
    PYTHON="python"
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
    print("Refusing to start monitor: requires dry_run: true, auto_reply.dry_run: true, allow_real_send: false.")
    print(f"config: {config_path}")
    sys.exit(2)
PY

pid_command() {
    ps -p "$1" -o command= 2>/dev/null || true
}

pid_matches() {
    local pid="$1"
    local command
    command="$(pid_command "$pid")"
    [[ "$command" == *"$MARKER"* ]]
}

running_pid_from_file() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid="$(tr -d '[:space:]' < "$PID_FILE")"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    if kill -0 "$pid" 2>/dev/null && pid_matches "$pid"; then
        echo "$pid"
        return 0
    fi
    rm -f "$PID_FILE"
    return 1
}

find_running_pid() {
    pgrep -f "$MARKER" 2>/dev/null | while read -r pid; do
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        [[ "$pid" == "$$" ]] && continue
        if pid_matches "$pid"; then
            echo "$pid"
            return 0
        fi
    done | head -n 1
}

if existing_pid="$(running_pid_from_file)"; then
    echo "auto-reply-monitor already running: pid=$existing_pid"
    exit 0
fi

if existing_pid="$(find_running_pid)" && [[ -n "$existing_pid" ]]; then
    echo "$existing_pid" > "$PID_FILE"
    echo "auto-reply-monitor already running: pid=$existing_pid"
    exit 0
fi

cd "$PROJECT_DIR"
nohup "$PYTHON" -u -m src.main auto-reply-monitor --dry-run --interval-seconds 60 >> "$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" > "$PID_FILE"
sleep 1

if kill -0 "$pid" 2>/dev/null && pid_matches "$pid"; then
    echo "auto-reply-monitor started: pid=$pid"
    echo "log: $LOG_FILE"
    exit 0
fi

echo "auto-reply-monitor failed to stay running. See log: $LOG_FILE"
rm -f "$PID_FILE"
tail -n 40 "$LOG_FILE" 2>/dev/null || true
exit 1
