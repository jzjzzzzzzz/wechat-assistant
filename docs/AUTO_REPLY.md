# Safe WeChat auto-reply

The default runtime remains dry-run. Real sending is disabled unless the operator explicitly changes both safety flags and the final send gate allows the target.

Default safety settings in `config/settings.yaml`:

- `auto_reply.enabled: false`
- `auto_reply.dry_run: true`
- `allow_real_send: false`
- `auto_reply.private_only: true`
- `auto_reply.require_private_chat_whitelist: true`
- `owner.status_default: online`

The planned reply text is:

```text
号主不在线～ AI自动回复的
```

## Detection

Before any auto-reply planning, the daemon OCR-checks the macOS top-right menu bar for the status menu:

- `🟢 OL`, `Online`, `WA ONLINE`, or `在线`: auto-reply system is active.
- `🔴 OFF`, `Offline`, `WA OFFLINE`, or `离线`: auto-reply system is inactive.
- unreadable, conflicting, or missing OCR: `unknown`, safe default no send.

The status is polled every daemon pass and again immediately before a ready reply is executed. State changes and allow/block decisions are logged.

Primary detection uses a screenshot of the likely macOS notification area and OCR. By default it skips the top menu-bar strip (`notification_ocr.skip_menu_bar_pixels`) so iBar/status-menu text such as `OL` or `OFF` is not treated as notification content. Candidates must look like WeChat notifications and meet `auto_reply.min_ocr_confidence`.

Fallback detection activates the already logged-in WeChat Mac app only when the explicit command runs, screenshots the left chat list, runs OCR, and looks for unread indicators. This fallback never reads WeChat databases or decrypted files.

Both paths produce `AutoReplyEvent` objects with:

- `source`: `notification_ocr` or `unread_chat_scan`
- `sender`
- `message_preview`
- timestamps for detected, first seen, and last seen
- `confidence`
- `status`
- `reason`
- `is_private_candidate`

## Policy

macOS status is the first gate:

- `online` / `OL`: candidates may proceed if every other safety check passes.
- `offline` / `OFF`: candidates are ignored with reason `system_offline`.
- `unknown`: candidates are ignored with reason `system_status_unknown`.

`delay_minutes` remains available for delayed modes. With `owner.offline_reply_immediate: true` kept for backward compatibility, online/OL mode can reply immediately after all gates pass.

Private-chat classification is conservative. A sender is treated as private only when:

- the sender is known and not `unknown`
- the sender does not match group/system/public-account blocklist keywords
- the sender does not match configured non-private keywords
- `auto_reply.require_private_chat_whitelist` is true and the sender is listed in `auto_reply.private_chat_whitelist` or `auto_reply.allowed_test_contacts`

Group/system/public-account filters run before whitelist matching. A group-like name in a whitelist is still blocked.

The default test private whitelist includes:

```yaml
private_chat_whitelist:
  - "爱"
allowed_test_contacts:
  - "文件传输助手"
```

The policy ignores:

- unknown senders
- low-confidence OCR results
- group chats and names matching configured blocklist keywords
- sender names that look like group chats by member-count suffix, such as `项目组(5)`, `项目组（5）`, `项目组（5人）`, `Study Group(12)`, or `Family（8人）`
- senders outside the private chat whitelist
- non-private candidates when `private_only` is true
- repeat plans for the same sender inside `cooldown_minutes`

In dry-run mode the daemon logs and prints:

```text
WOULD AUTO REPLY
Target: sender
Message: 号主不在线～ AI自动回复的
```

## Commands

```bash
python -m src.main auto-reply-plan
python -m src.main notification-check --once
python -m src.main unread-scan --once
python -m src.main auto-reply-daemon --dry-run --once
python -m src.main auto-reply-daemon --dry-run
python -m src.main owner-status
python -m src.main owner-status set online
python -m src.main owner-status set offline
python -m src.main status-menu --check
python -m src.main status-menu
python -m src.main macos-status-check --once
python -m src.main private-whitelist list
python -m src.main sender-classify 爱 "项目组(5)" "Official Accounts"
python -m src.main auto-reply-monitor --dry-run --interval-seconds 60 --minutes 60
```

`auto-reply-daemon --dry-run --once` runs one notification pass, one unread-list fallback pass, applies policy, prints planned actions, writes logs, and exits.

`auto-reply-daemon --dry-run` polls until Ctrl+C and respects `poll_interval_seconds`.

`macos-status-check --once` captures only the top-right menu bar area, OCRs the OL/OFF label, prints the detected status, and exits. It does not scan WeChat, update the database, or send messages.

`sender-classify` is a safe local policy check. It does not scan WeChat, OCR screenshots, send messages, or control the UI.

`status-menu` only reads/writes owner status. The visible macOS menu-bar title is intentionally short for iBar-managed menu bars:

- online: `🟢 OL`
- offline: `🔴 OFF`

## Explicit non-goals

This milestone never:

- reads WeChat databases
- decrypts WeChat files
- extracts credentials, cookies, tokens, passwords, or sessions
- bypasses WeChat security
- sends a real auto-reply
- auto-replies to groups, public accounts, subscriptions, service notifications, or system messages

If macOS Screen Recording or Accessibility permissions are missing, detection fails safely and logs a clear message.

## Real-send testing boundary

Real auto-reply testing must only target `文件传输助手` / `File Transfer` unless a future explicit whitelist entry is added. Every real auto-reply must pass:

- current top-right status is online/OL
- sender is not a group chat
- sender is known and passes whitelist checks
- sender is allowed by `allowed_real_contacts`
- OCR confidence is above `auto_reply.min_ocr_confidence`
- the final gate logs the send reason
