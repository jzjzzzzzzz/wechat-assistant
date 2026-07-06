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
  state_stale_minutes: 1440
  private_only: true
  reply_message: "号主不在线～ AI自动回复的"
  detection_priority:
    - "notification_ocr"
    - "unread_chat_scan"
  allowed_test_contacts:
    - "文件传输助手"
  require_private_chat_whitelist: true
  private_chat_whitelist:
    - "爱"
  blocklist_keywords:
    - "群聊"
    - "群"
    - "服务通知"
    - "订阅号"
    - "公众号"
    - "微信支付"
    - "微信团队"
  non_private_keywords:
    - "Official Accounts"
    - "Service Accounts"
    - "WeChat Pay"
    - "WeChat Team"
    - "Subscriptions"
    - "Subscription"
    - "公众号"
    - "订阅号"
    - "服务通知"
    - "微信支付"
    - "微信团队"
  min_ocr_confidence: 0.65

owner:
  status_default: "online"
  offline_reply_immediate: true
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

It runs only from explicit commands or daemon polling. The preferred path finds a visible WeChat window in the background, captures the window or visible bounds, verifies the screenshot is likely WeChat, then uses OCR/OpenCV-style visual inspection to extract likely chat names and unread red badges.

Activation fallback is disabled by default. The scanner must not inspect WeChat storage.

## Policy

The policy decides whether a candidate is ignored, pending, or ready for dry-run reply planning.

- Owner `online` ignores candidates with reason `owner_online`.
- Owner `offline` can make whitelisted private candidates ready immediately when `owner.offline_reply_immediate` is true.
- `delay_minutes` remains available for future delayed modes.
- Duplicate reply plans for the same sender are blocked for `cooldown_minutes`.
- `private_only` rejects non-private candidates.
- `require_private_chat_whitelist` rejects senders outside `private_chat_whitelist`.
- Group/system/public-account keywords are enforced before whitelist acceptance.
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
python -m src.main owner-status
python -m src.main auto-reply-monitor --dry-run --interval-seconds 60 --minutes 60
```

The one-pass daemon command loads config, runs notification detection, runs fallback unread scanning, applies policy, prints planned dry-run actions, writes logs, sends nothing, and exits cleanly.
