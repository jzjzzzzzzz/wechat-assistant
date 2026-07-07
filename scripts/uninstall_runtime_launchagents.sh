#!/usr/bin/env bash
set -euo pipefail

LAUNCHAGENTS_DIR="${WECHAT_ASSISTANT_LAUNCHAGENTS_DIR:-$HOME/Library/LaunchAgents}"
DOMAIN="${WECHAT_ASSISTANT_LAUNCHCTL_DOMAIN:-gui/$UID}"

STATUS_LABEL="com.wechat-assistant.status-menu"
DAEMON_LABEL="com.wechat-assistant.auto-reply-daemon"
STATUS_TARGET="$LAUNCHAGENTS_DIR/$STATUS_LABEL.plist"
DAEMON_TARGET="$LAUNCHAGENTS_DIR/$DAEMON_LABEL.plist"

remove_agent() {
    local label="$1"
    local target="$2"
    launchctl bootout "$DOMAIN" "$target" 2>/dev/null || true
    rm -f "$target"
    echo "Removed LaunchAgent: $target"
    echo "Label: $label"
}

remove_agent "$STATUS_LABEL" "$STATUS_TARGET"
remove_agent "$DAEMON_LABEL" "$DAEMON_TARGET"

echo "Runtime LaunchAgents removed."
