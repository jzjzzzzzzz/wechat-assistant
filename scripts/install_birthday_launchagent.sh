#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$PROJECT_DIR/launchd/com.wechat-assistant.birthday.plist.template"
TARGET="$HOME/Library/LaunchAgents/com.wechat-assistant.birthday.plist"
LABEL="com.wechat-assistant.birthday"
DOMAIN="gui/$UID"

mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/logs"

sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$TEMPLATE" > "$TARGET"

launchctl bootout "$DOMAIN" "$TARGET" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$TARGET"
launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl kickstart -k "$DOMAIN/$LABEL"

echo "Installed LaunchAgent: $TARGET"
echo "Label: $LABEL"
