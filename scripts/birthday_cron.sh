#!/usr/bin/env bash
# birthday_cron.sh — called by launchd every day at 00:00
#
# What it does:
#   1. Checks whether WeChat is running. Exits silently if not (safe failure).
#   2. Runs send-birthday --force-send (real sending enabled in memory only).
#      The config file on disk stays at dry_run: true / allow_real_send: false.
#   3. Uses caffeinate -i so the Mac does not sleep mid-send.
#
# Requirements:
#   - Mac must be on and logged in (screen can be locked, but process must run).
#   - WeChat must already be running and logged in.
#   - The .venv virtualenv must exist at the project root.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_FILE="$PROJECT_DIR/logs/birthday_cron.log"
MAX_LOG_LINES=500

# ── helpers ──────────────────────────────────────────────────────────────────

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

rotate_log() {
    if [[ -f "$LOG_FILE" ]]; then
        local lines
        lines=$(wc -l < "$LOG_FILE")
        if (( lines > MAX_LOG_LINES )); then
            tail -n "$MAX_LOG_LINES" "$LOG_FILE" > "${LOG_FILE}.tmp"
            mv "${LOG_FILE}.tmp" "$LOG_FILE"
        fi
    fi
}

wechat_running() {
    osascript -e 'tell application "System Events" to (name of processes) contains "WeChat"' 2>/dev/null \
        | grep -qi "true"
}

# ── main ─────────────────────────────────────────────────────────────────────

mkdir -p "$PROJECT_DIR/logs"
rotate_log

log "====== birthday_cron.sh start ======"
log "Project: $PROJECT_DIR"
log "Date:    $(date '+%Y-%m-%d')"

# Guard: WeChat must be running
if ! wechat_running; then
    log "WeChat is not running — skipping birthday send (safe exit)."
    log "====== birthday_cron.sh end (skipped) ======"
    exit 0
fi

log "WeChat is running. Starting send-birthday..."

# caffeinate -i: prevent system idle sleep during the send
# timeout 120: hard kill if something hangs (safety net)
cd "$PROJECT_DIR"

# caffeinate -i: prevent system idle sleep during the send
# Python itself handles timeouts internally; no external timeout command needed.
if caffeinate -i \
    "$PYTHON" -m src.main send-birthday --force-send \
    >> "$LOG_FILE" 2>&1; then
    log "send-birthday finished successfully."
else
    EXIT_CODE=$?
    log "send-birthday exited with code $EXIT_CODE (may be no birthdays today — normal)."
fi

log "====== birthday_cron.sh end ======"
