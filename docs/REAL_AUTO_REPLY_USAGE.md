# Real auto-reply usage

This repository is currently configured for local real-send operation on the
owner's Mac:

```yaml
dry_run: false
allow_real_send: true

auto_reply:
  enabled: true
  dry_run: false

unread_scan:
  enable_scroll_scan: true
  max_scroll_pages: 20
```

Real sending is still gated. The assistant must see an allowed unread private
chat and must pass the final send gate before it pastes or presses Enter.

## Current Reply Direction

The current product behavior is:

- `online` / `OL`: owner is present, auto-reply is blocked.
- `offline` / `OFF`: owner is away, valid unread private chats may be replied to.
- `unknown`: blocked.

The owner status is stored in the local SQLite database and can be changed by
the floating status window or the CLI. The daemon reads it on every pass and
again before executing a ready reply.

## Required macOS Permissions

Grant permissions to the app that runs Python, usually Terminal, iTerm2,
Cursor, or VS Code:

- Screen Recording: required for screenshots, OCR, Dock unread checks, and
  WeChat window verification.
- Accessibility: required for keyboard/mouse control, WeChat search, paste, and
  Enter.
- Automation: may be requested by macOS when AppleScript or app activation is
  used.

After changing these permissions, quit and reopen the terminal app.

## Start The Status Control

The floating status window is the recommended control because iBar/menu-bar
titles may not refresh in real time.

```bash
cd ~/学习资料/wechat-assistant
source .venv/bin/activate
scripts/start_status_window.sh
```

The button shows:

- `OL`: owner online, no auto-reply.
- `OFF`: owner offline, auto-reply may run after all gates pass.

You can also use CLI status commands:

```bash
python -m src.main owner-status
python -m src.main owner-status set online
python -m src.main owner-status set offline
python -m src.main owner-status toggle
```

## One-Pass Real Drain

Use the drain command when there is a visible unread WeChat Dock red badge and
you want the assistant to process unread private messages until the Dock badge
disappears or the pass limit is reached.

```bash
python -m src.main owner-status set offline
python -m src.main auto-reply-drain --max-passes 10 --interval-seconds 2
python -m src.main owner-status set online
```

The drain command:

1. Confirms real-send mode is enabled.
2. Confirms the Dock unread badge safety signal is enabled.
3. Checks whether the WeChat Dock icon currently has a red unread badge.
4. Activates WeChat before scanning.
5. Captures and verifies the visible WeChat window.
6. Scans the current left chat list for red unread badges.
7. Scrolls the left chat list up to `unread_scan.max_scroll_pages` pages.
8. Re-activates WeChat before each scrolled page scan.
9. Associates each red badge with a chat row.
10. OCRs the sender-name region.
11. Rejects unknown senders, low-confidence OCR, blocklisted accounts, group
    chats, and non-whitelisted senders.
12. Searches WeChat for the target sender.
13. Verifies the opened chat by OCRing the sidebar row and title bar.
14. Sends the configured reply only after the final gate passes.
15. Re-checks the Dock unread badge and repeats until it clears or max passes
    are reached.

## Long-Running Real Daemon

For continuous operation in the foreground terminal:

```bash
python -m src.main owner-status set offline
caffeinate -dimsu python -m src.main auto-reply-daemon
```

Stop with `Ctrl+C`.

The daemon runs every `auto_reply.poll_interval_seconds`, currently 5 seconds.
It uses the same policy and final send gate as the drain command. It does not
reply while owner status is `online` or `unknown`.

## Allowed Real Targets

Real sends are limited to explicit contacts in `allowed_real_contacts`.
The current local list includes:

```yaml
allowed_real_contacts:
  - "File Transfer"
  - "文件传输助手"
  - "爱"
```

Private auto-reply candidates must also pass `auto_reply.private_chat_whitelist`:

```yaml
auto_reply:
  require_private_chat_whitelist: true
  private_chat_whitelist:
    - "爱"
```

Do not add broad names or group names to these lists.

## Group Chat Blocking

The classifier blocks group-like names before whitelist matching. A sender is
treated as a group chat and cannot be replied to if the name ends with
parentheses containing a number.

Blocked examples:

- `项目组(5)`
- `项目组（5）`
- `项目组（5人）`
- `Study Group(12)`
- `Family（8人）`

Configured blocklist and non-private keywords also block service accounts,
public accounts, subscriptions, WeChat Pay, WeChat Team, and other system-like
senders.

If OCR is uncertain or the sender is unknown, the safe behavior is no send.

## Diagnostics

Check current runtime state:

```bash
python -m src.main runtime-status
python -m src.main auto-reply-plan
```

Check one unread scan without sending:

```bash
python -m src.main unread-scan --once
```

Check Dock unread badge detection:

```bash
python -m src.main dock-unread-check --once
```

Inspect logs:

```bash
tail -n 120 logs/app.log
tail -n 120 logs/auto_reply_monitor.log
python -m src.main auto-reply-state list
```

Debug screenshots are saved under:

```text
screenshots/background_scan/
screenshots/dock_scan/
```

These files are ignored by Git.

## Stop Or Return To Safe Mode

Return owner status to online:

```bash
python -m src.main owner-status set online
```

Return the repository config to dry-run:

```yaml
dry_run: true
allow_real_send: false

auto_reply:
  enabled: false
  dry_run: true
```

Then verify:

```bash
python -m src.main runtime-status
python -m src.main auto-reply-plan
```
