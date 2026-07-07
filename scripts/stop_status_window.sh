#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${WECHAT_ASSISTANT_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
PID_FILE="$PROJECT_DIR/run/status_window.pid"
MARKER="src.main status-window"
LABEL="com.wechat-assistant.status-window"
LAUNCHAGENTS_DIR="${WECHAT_ASSISTANT_LAUNCHAGENTS_DIR:-$HOME/Library/LaunchAgents}"
TARGET="$LAUNCHAGENTS_DIR/$LABEL.plist"
DOMAIN="${WECHAT_ASSISTANT_LAUNCHCTL_DOMAIN:-gui/$UID}"

if command -v launchctl >/dev/null 2>&1 && [[ -f "$TARGET" ]]; then
    launchctl bootout "$DOMAIN" "$TARGET" 2>/dev/null || true
fi

pid_command() {
    ps -p "$1" -o command= 2>/dev/null || true
}

pid_matches() {
    local pid="$1"
    local command
    command="$(pid_command "$pid")"
    [[ "$command" == *"$MARKER"* ]]
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

pid=""
if [[ -f "$PID_FILE" ]]; then
    pid="$(tr -d '[:space:]' < "$PID_FILE")"
    if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
        echo "status-window pid file is invalid; removing stale pid file."
        rm -f "$PID_FILE"
        pid=""
    elif ! kill -0 "$pid" 2>/dev/null; then
        echo "status-window pid file is stale; removing stale pid file."
        rm -f "$PID_FILE"
        pid=""
    elif ! pid_matches "$pid"; then
        echo "status-window pid $pid does not match this project command; removing stale pid file."
        rm -f "$PID_FILE"
        pid=""
    fi
fi

if [[ -z "$pid" ]]; then
    pid="$(find_running_pid || true)"
fi

if [[ -z "$pid" ]]; then
    echo "status-window is not running."
    exit 0
fi

kill "$pid"
for _ in {1..50}; do
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        echo "status-window stopped: pid=$pid"
        exit 0
    fi
    sleep 0.1
done

echo "status-window stop timed out: pid=$pid"
exit 1
