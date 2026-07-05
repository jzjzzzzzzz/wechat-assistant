# Auto-reply architecture

This architecture is for a dry-run-only milestone. The assistant may detect and plan an auto-reply, but it must not send a WeChat message.

## Safety invariants

- `dry_run` stays true by default.
- `allow_real_send` stays false by default.
- Auto-reply code must not call the real message sender.
- Auto-reply code must not read WeChat databases.
- Auto-reply code must not decrypt files.
- Auto-reply code must not extract passwords, cookies, tokens, sessions, or other credentials.
- Auto-reply code must not bypass WeChat security.
- Imports and pytest must not perform WeChat UI actions.
- Long-running loops must have a one-pass command path.

## Configuration

The `auto_reply` section in `config/settings.yaml` controls this feature:

```yaml
auto_reply:
  enabled: false
  dry_run: true
  delay_minutes: 5
  poll_interval_seconds: 5
  cooldown_minutes: 60
  private_only: true
  reply_message: "号主不在线～ AI自动回复的"
  detection_priority:
    - "notification_ocr"
    - "unread_chat_scan"
  allowed_test_contacts:
    - "文件传输助手"
  blocklist_keywords:
    - "群聊"
    - "群"
    - "服务通知"
    - "订阅号"
    - "公众号"
    - "微信支付"
    - "微信团队"
  min_ocr_confidence: 0.65
```

The daemon must force in-memory dry-run safety for this milestone even if a caller passes unsafe runtime values.

## Event model

Detection paths must produce unified `AutoReplyEvent` values:

- `source`: `notification_ocr` or `unread_chat_scan`
- `sender`: display name or `unknown`
- `message_preview`: best-effort text preview or empty string
- `detected_at`
- `first_seen_at`
- `last_seen_at`
- `confidence`
- `status`: `pending`, `ready_for_reply`, `ignored`, or `expired`
- `reason`
- `is_private_candidate`

## Primary detection

`notification_ocr` is the primary strategy.

It captures the likely macOS notification area, runs OCR, checks for a WeChat marker, extracts sender and preview best-effort, filters low-confidence and blocked candidates, and emits dry-run candidate events only. Missing Screen Recording permission must be logged clearly and return no events instead of crashing.

## Fallback detection

`unread_chat_scan` is the fallback strategy.

It runs only from explicit commands or daemon polling, activates the already logged-in WeChat Mac UI, screenshots the left chat list, uses OCR/OpenCV-style visual inspection where available, extracts likely chat names, and filters groups, public accounts, service notifications, subscriptions, and system messages. It must not inspect WeChat storage.

## Policy

The policy decides whether a candidate is still pending, ignored, or ready for dry-run reply planning.

- A candidate becomes `ready_for_reply` only after `delay_minutes`.
- Duplicate reply plans for the same sender are blocked for `cooldown_minutes`.
- `private_only` rejects non-private candidates.
- Unknown senders are ignored.
- Low OCR confidence is ignored.
- Blocklist keywords are enforced.

For a ready event, dry-run output is:

```text
WOULD AUTO REPLY
Target: sender
Message: 号主不在线～ AI自动回复的
```

## CLI

Required safe commands:

```bash
python -m src.main auto-reply-plan
python -m src.main notification-check --once
python -m src.main unread-scan --once
python -m src.main auto-reply-daemon --dry-run --once
python -m src.main auto-reply-daemon --dry-run
```

The one-pass daemon command loads config, runs notification detection, runs fallback unread scanning, applies policy, prints planned dry-run actions, writes logs, sends nothing, and exits cleanly.
