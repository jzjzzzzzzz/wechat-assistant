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

## OCR Status Window

Because menu bar managers such as iBar may hide or delay-refresh third-party menu titles, the recommended OCR status source is the project's own transparent floating status control below iBar:

```bash
scripts/start_status_window.sh
```

The window displays large OCR-friendly text below the iBar area:

- online: `OL`
- offline: `OFF`

Controls:

- `OL` / `OFF` button: toggles owner status immediately.
- `LOCK` / `UNLOCK` button: controls whether the window is locked in front of other windows.

It refreshes from `owner_status` every second by default:

```yaml
owner:
  status_window_enabled: true
  status_window:
    width: 220
    height: 46
    margin_right: 24
    margin_top: 142
    refresh_seconds: 1
    locked_on_top: true
```

Stop it:

```bash
scripts/stop_status_window.sh
```

The status window only reads/writes local owner status. It does not scan WeChat, OCR WeChat, send messages, click chats, type, or press Enter.

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

This installs three user LaunchAgents:

- `com.wechat-assistant.status-menu`: runs `python -u -m src.main status-menu`
- `com.wechat-assistant.status-window`: runs `python -u -m src.main status-window`
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
- status window: `logs/status_window_launchagent.log`
- dry-run daemon: `logs/auto_reply_daemon_launchagent.log`

The LaunchAgent daemon is dry-run only. It does not enable real sending.

## Status OCR Check

Check the live status-window screenshot detector without scanning WeChat:

```bash
python -m src.main macos-status-check --once
```

Expected examples:

```text
raw_status: active
db_status: online
detected_text: 🟢 OL
safe_to_auto_reply: False
```

`raw_status: inactive` / `db_status: offline` is the owner-away state where auto-reply may proceed after every other gate passes. If it prints `raw_status: unknown`, the safe behavior is no auto-reply. Enable Screen Recording permission or make the status window visible.

The status detector captures only the expected `OL` / `OFF` button area. This avoids OCRing arbitrary application text behind the transparent window:

```yaml
macos_status:
  capture_status_window_button: true
  capture_padding_x: 8
  capture_padding_y: 6
  capture_width: 560
  capture_height: 220
```

`capture_width` and `capture_height` are fallback values used only if dedicated status-window button capture is disabled.

The long-running daemon uses the local owner-status database by default because iBar/menu-bar visibility can be delayed or hidden by macOS:

```yaml
macos_status:
  enabled: false
```

Set `macos_status.enabled: true` only if the visible OL/OFF status control is reliably capturable on your machine.

Check the bottom Dock unread-badge safety signal without scanning WeChat:

```bash
python -m src.main dock-unread-check --once
```

This captures only the bottom Dock strip, looks for a red badge attached to a WeChat-like green icon, writes debug masks/overlays under `screenshots/dock_scan/`, and exits.

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

## Safe Real-send Test

Keep real sending disabled until you explicitly run a forced real-send test.

Minimum config conditions for a future real-send test:

- `dry_run: false`
- `auto_reply.dry_run: false`
- `allow_real_send: true`
- `allowed_real_contacts` contains the exact target, such as `文件传输助手` / `File Transfer` or `爱`
- owner status says `offline` / `OFF`
- Dock unread safety confirms a WeChat red unread badge when enabled
- sender classification is private, not group
- WeChat is confirmed frontmost before `⌘F`
- the opened chat is OCR-verified in both sidebar and title-bar regions before paste/Enter

If EasyOCR consistently misreads a short title bar name, add the correction to
`contact_ocr_aliases`. This does not bypass confirmation; it only lets the title
bar verifier recognize a known OCR shape for the exact requested target.

Manual one-off test command:

```bash
python -m src.main test-send --force-send --contact 爱
```

Do not test real sends against groups.

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
