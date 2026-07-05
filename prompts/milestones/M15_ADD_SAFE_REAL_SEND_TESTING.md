# M15 Add Safe Real Send Testing

## 1. Goal

Add a strictly controlled real-send test path for `文件传输助手` only.

## 2. Context

Real sending must be tested carefully after dry-run flows, UI automation, state detection, and logging are stable.

## 3. Current Repository Assumptions

- Message sender has safety gates.
- UI automation is stable.
- Audit logging may exist.

## 4. Files Likely To Modify

- `src/message_sender.py`
- `src/wechat_window.py`
- `src/scheduler.py`
- tests
- README

## 5. Detailed Implementation Steps

1. Confirm current config gates.
2. Add explicit test-send command documentation for real-send test.
3. Require target exactly `文件传输助手`.
4. Print `REAL SEND ENABLED`, target, and message.
5. Add screenshot before and after send if practical.
6. Add audit event.
7. Add mocked tests for real-send sequence.
8. Run `pytest`.

## 6. Safety Requirements

- Only `文件传输助手` can be real-send target.
- Both `dry_run: false` and `allow_real_send: true` are required.
- No scheduler real-send to normal contacts.

## 7. Testing Requirements

- Test real-send blocked by dry-run.
- Test real-send blocked by allow flag.
- Test real-send blocked for normal contact.
- Test allowed mocked sequence for `文件传输助手`.
- Run `pytest`.

## 8. Git Branch Name

`feature/safe-real-send-testing`

## 9. Commit Message

`Add safe real send testing path`

## 10. Acceptance Criteria

- Real-send path remains test-only.
- README explains exact risk and settings.
- Tests pass.

## 11. What Not To Do

- Do not enable normal-contact real sends.
- Do not add bulk sends.
- Do not hide warnings.

## 12. Final Report Format

Report safety gates, exact manual test command, tests, audit evidence, and limitations.
