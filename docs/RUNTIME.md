# Runtime operations

These commands manage local helper processes only. They do not enable real WeChat sending.

## Safety defaults

- `dry_run: true`
- `auto_reply.dry_run: true`
- `allow_real_send: false`
- `owner.status_default: online`
- `unread_scan.enable_scroll_scan: false`

Real auto-reply sending is disabled in this milestone.

Auto-reply status semantics:

- `🟢 OL` / `Online`: auto-reply system active; candidates may proceed through the remaining gates.
- `🔴 OFF` / `Offline`: auto-reply system inactive; no auto-reply.
- unknown or conflicting OCR: no auto-reply.

## macOS Permissions

Grant these permissions to the terminal app or packaged app that runs the assistant:

- Screen Recording: required for menu-bar status OCR, notification OCR, and WeChat window screenshots.
- Accessibility: required for any controlled UI actions and future safe real-send testing.
- Automation: may be required by macOS if AppleScript/GUI automation fallback is used.

After changing permissions, restart the terminal app.

## Status Menu

Start the macOS owner-status menu:

```bash
scripts/start_status_menu.sh
```

The menu title is intentionally short for iBar:

- online: `🟢 OL`
- offline: `🔴 OFF`

The script writes:

- PID: `run/status_menu.pid`
- log: `logs/status_menu.log`

Stop it:

```bash
scripts/stop_status_menu.sh
```

The menu app only reads and writes `owner_status`. It does not scan WeChat, run OCR, send messages, click chats, type, or press Enter.

While running, the menu app refreshes its title from the database every second by default:

```yaml
owner:
  status_menu_refresh_seconds: 1
```

If you change status with `owner-status set online/offline`, the top-right label should follow on the next refresh tick.

## Dry-run Monitor

Start the dry-run monitor:

```bash
scripts/start_monitor.sh
```

The script refuses to start unless the config has:

- `dry_run: true`
- `auto_reply.dry_run: true`
- `allow_real_send: false`

The script writes:

- PID: `run/auto_reply_monitor.pid`
- log: `logs/auto_reply_monitor.log`
- events: `logs/auto_reply_events.jsonl`

Stop it:

```bash
scripts/stop_monitor.sh
```

The monitor stays dry-run only. It may detect candidates and print/log `WOULD AUTO REPLY`, but it does not send messages.

This script is useful for manual observation and bounded soak tests. For a process that survives terminal exits and restarts at login, use the LaunchAgent setup below.

## Long-Running LaunchAgents

Install the long-running runtime agents:

```bash
scripts/install_runtime_launchagents.sh
```

This installs two user LaunchAgents:

- `com.wechat-assistant.status-menu`: runs `python -u -m src.main status-menu`
- `com.wechat-assistant.auto-reply-daemon`: runs `python -u -m src.main auto-reply-daemon --dry-run`

The installer refuses to run unless the config is still safe:

- `dry_run: true`
- `auto_reply.dry_run: true`
- `allow_real_send: false`

Remove both runtime agents:

```bash
scripts/uninstall_runtime_launchagents.sh
```

Inspect launchd state:

```bash
launchctl print gui/$UID/com.wechat-assistant.status-menu
launchctl print gui/$UID/com.wechat-assistant.auto-reply-daemon
```

LaunchAgent logs:

- status menu: `logs/status_menu_launchagent.log`
- dry-run daemon: `logs/auto_reply_daemon_launchagent.log`

The LaunchAgent daemon is dry-run only. It does not enable real sending.

## Status OCR Check

Check the live top-right menu-bar status without scanning WeChat:

```bash
python -m src.main macos-status-check --once
```

Expected examples:

```text
raw_status: active
db_status: online
detected_text: 🟢 OL
safe_to_auto_reply: True
```

If it prints `raw_status: unknown`, the safe behavior is no auto-reply. Enable Screen Recording permission or make the iBar/status-menu item visible.

The status detector captures only a shallow top menu-bar strip. By default it reads the rightmost 1400px so iBar can keep `🟢 OL` / `🔴 OFF` visible even when it is not directly next to the clock:

```yaml
macos_status:
  capture_width: 1400
  capture_height: 34
```

## Runtime Status

Check owner status, process state, logs, safety flags, and database path:

```bash
python -m src.main runtime-status
```

Stop both helper processes:

```bash
python -m src.main runtime-stop-all
```

## Dry-run Auto-reply

One safe pass:

```bash
python -m src.main auto-reply-daemon --dry-run --once
```

Long-running dry-run:

```bash
python -m src.main auto-reply-daemon --dry-run
```

The daemon polls OL/OFF every pass and again before executing a ready dry-run action.

## Safe File Transfer Real-send Test

Keep real sending disabled until you explicitly test `文件传输助手`.

Minimum config conditions for a future real-send test:

- `dry_run: false`
- `auto_reply.dry_run: false`
- `allow_real_send: true`
- `allowed_real_contacts` contains only `文件传输助手` / `File Transfer` unless a future explicit whitelist is intended
- top-right status OCR says `online` / `OL`
- sender classification is private, not group

Do not test real sends against normal contacts or groups.

## Confirming Blocks

Confirm groups are blocked:

```bash
python -m src.main sender-classify "项目组(5)" "项目组（5）" "项目组（5人）" "Study Group(12)" "Family（8人）"
```

All should report `category: group_candidate`.

Manage the private whitelist:

```bash
python -m src.main private-whitelist list
python -m src.main private-whitelist add "爱"
python -m src.main private-whitelist remove "爱"
```

Whitelist entries are considered private only after group/system/public-account filters pass. A group-like name in the whitelist is still blocked.

Confirm OFF blocks:

```bash
python -m src.main owner-status set offline
python -m src.main auto-reply-daemon --dry-run --once
python -m src.main owner-status set online
```

When live status OCR is unavailable or shows OFF, the daemon logs a block reason and does not emit an actionable reply.

## Keeping The Mac Awake

For manual long runs, keep the Mac awake with `caffeinate`:

```bash
caffeinate -dimsu scripts/start_monitor.sh
```

Or run the monitor command directly for a bounded session:

```bash
caffeinate -dimsu python -m src.main auto-reply-monitor --dry-run --interval-seconds 60 --minutes 60
```

## Logs

Useful paths:

- app log: `logs/app.log`
- status menu log: `logs/status_menu.log`
- monitor log: `logs/auto_reply_monitor.log`
- monitor JSONL events: `logs/auto_reply_events.jsonl`
- SQLite database: `data/wechat_assistant.sqlite3`
