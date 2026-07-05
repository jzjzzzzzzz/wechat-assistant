# M09 Add History and Audit Logs

## 1. Goal

Add structured audit records for safety decisions, dry-runs, blocked sends, and future real-send tests.

## 2. Context

Plain logs are useful, but structured audit history helps GUI review and safety accountability.

## 3. Current Repository Assumptions

- Logging exists.
- SQLite may exist.
- Message sender has safety gates.

## 4. Files Likely To Modify

- `src/logger.py`
- `src/message_sender.py`
- `src/database.py`
- new `src/audit.py`
- tests

## 5. Detailed Implementation Steps

1. Define audit event types.
2. Record dry-run message attempts.
3. Record blocked real sends.
4. Record screenshot paths when available.
5. Add repository methods.
6. Keep logs concise and structured.
7. Add tests.
8. Run `pytest`.

## 6. Safety Requirements

- Do not store credentials.
- Avoid storing full sensitive conversations.
- Audit records must not enable sending.

## 7. Testing Requirements

- Test event creation.
- Test blocked send audit.
- Test dry-run audit.
- Run `pytest`.

## 8. Git Branch Name

`feature/history-audit-logs`

## 9. Commit Message

`Add history and audit logging`

## 10. Acceptance Criteria

- Safety decisions are auditable.
- Tests confirm audit records are written.
- Existing logging still works.

## 11. What Not To Do

- Do not log secrets.
- Do not store private full chat history.
- Do not read WeChat history.

## 12. Final Report Format

Report event types, storage path, tests, privacy choices, and limitations.
