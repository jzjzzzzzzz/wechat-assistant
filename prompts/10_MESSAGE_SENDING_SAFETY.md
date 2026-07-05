# Message Sending Safety Prompt

## Goal

Keep message sending safe, explicit, auditable, and reversible during development.

## Required Gates

Real sending is allowed only when:

```yaml
dry_run: false
allow_real_send: true
```

And the initial real target is:

```text
文件传输助手
```

## Dry-Run Requirements

Dry-run must:

- Not press Enter to send.
- Prefer not to touch the WeChat input box unless a future test explicitly needs UI rehearsal.
- Print the target and message preview.
- Log the safety decision.
- Return success if the planned action is valid.

## Real-Send Requirements

Real-send must:

- Print `REAL SEND ENABLED`.
- Print target and message.
- Search target using keyboard shortcuts.
- Paste with clipboard.
- Press Enter only after all gates pass.
- Capture screenshot after sending.
- Log all retry attempts.

## Tests

Always test:

- dry-run does not call real UI actions
- `allow_real_send: false` blocks sending
- non-`文件传输助手` target blocks real sending
- real-send path calls search, paste, enter, screenshot in order when mocked
