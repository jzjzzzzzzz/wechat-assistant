# Runtime operations

These commands manage local helper processes only. They do not enable real WeChat sending.

## Safety defaults

- `dry_run: true`
- `auto_reply.dry_run: true`
- `allow_real_send: false`
- `owner.status_default: online`
- `unread_scan.enable_scroll_scan: false`

Real auto-reply sending is disabled in this milestone.

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

## Runtime Status

Check owner status, process state, logs, safety flags, and database path:

```bash
python -m src.main runtime-status
```

Stop both helper processes:

```bash
python -m src.main runtime-stop-all
```

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
