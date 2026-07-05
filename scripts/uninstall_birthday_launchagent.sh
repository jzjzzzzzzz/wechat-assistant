#!/usr/bin/env bash
set -euo pipefail

TARGET="$HOME/Library/LaunchAgents/com.wechat-assistant.birthday.plist"
DOMAIN="gui/$UID"
LABEL="com.wechat-assistant.birthday"

launchctl bootout "$DOMAIN" "$TARGET" 2>/dev/null || true
rm -f "$TARGET"

echo "Removed LaunchAgent: $TARGET"
echo "Label: $LABEL"
