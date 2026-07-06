#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${WECHAT_ASSISTANT_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
PID_FILE="$PROJECT_DIR/run/status_menu.pid"
LOG_FILE="$PROJECT_DIR/logs/status_menu.log"
MARKER="src.main status-menu"

mkdir -p "$PROJECT_DIR/run" "$PROJECT_DIR/logs"

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
    echo "status-menu already running: pid=$existing_pid"
    exit 0
fi

if existing_pid="$(find_running_pid)" && [[ -n "$existing_pid" ]]; then
    echo "$existing_pid" > "$PID_FILE"
    echo "status-menu already running: pid=$existing_pid"
    exit 0
fi

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

cd "$PROJECT_DIR"
nohup "$PYTHON" -u -m src.main status-menu >> "$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" > "$PID_FILE"
sleep 1

if kill -0 "$pid" 2>/dev/null && pid_matches "$pid"; then
    echo "status-menu started: pid=$pid"
    echo "log: $LOG_FILE"
    exit 0
fi

echo "status-menu failed to stay running. See log: $LOG_FILE"
rm -f "$PID_FILE"
tail -n 40 "$LOG_FILE" 2>/dev/null || true
exit 1
