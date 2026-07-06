# Dry-run WeChat auto-reply

This milestone plans auto-replies only. It does not send WeChat messages.

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

Primary detection uses a screenshot of the likely macOS notification area and OCR. Candidates must look like WeChat notifications and meet `auto_reply.min_ocr_confidence`.

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

Owner status is the first gate:

- `online`: candidates may be detected, but they are ignored with reason `owner_online`.
- `offline`: whitelisted private candidates can become `ready_for_reply` immediately in dry-run mode when `owner.offline_reply_immediate` is true.

`delay_minutes` remains available for future delayed modes, but offline immediate mode overrides it.

Private-chat classification is conservative. A sender is treated as private only when:

- the sender is known and not `unknown`
- the sender does not match group/system/public-account blocklist keywords
- the sender does not match configured non-private keywords
- `auto_reply.require_private_chat_whitelist` is true and the sender is listed in `auto_reply.private_chat_whitelist`

The default test private whitelist includes:

```yaml
private_chat_whitelist:
  - "爱"
```

The policy ignores:

- unknown senders
- low-confidence OCR results
- group chats and names matching configured blocklist keywords
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
python -m src.main auto-reply-monitor --dry-run --interval-seconds 60 --minutes 60
```

`auto-reply-daemon --dry-run --once` runs one notification pass, one unread-list fallback pass, applies policy, prints planned actions, writes logs, and exits.

`auto-reply-daemon --dry-run` polls until Ctrl+C and respects `poll_interval_seconds`.

## Explicit non-goals

This milestone never:

- reads WeChat databases
- decrypts WeChat files
- extracts credentials, cookies, tokens, passwords, or sessions
- bypasses WeChat security
- sends a real auto-reply
- auto-replies to groups, public accounts, subscriptions, service notifications, or system messages

If macOS Screen Recording or Accessibility permissions are missing, detection fails safely and logs a clear message.
