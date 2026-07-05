# M07 Build Birthday Scheduler

## 1. Goal

Expand the birthday scheduler into a tested dry-run scheduling system.

## 2. Context

The current scheduler can read CSV and match today's birthday. It should become more robust before any real messaging.

## 3. Current Repository Assumptions

- `src/scheduler.py` exists.
- Message sending remains safety-gated.
- Birthday tasks are local project data.

## 4. Files Likely To Modify

- `src/scheduler.py`
- `src/message_sender.py`
- `data/birthday_tasks.csv`
- tests

## 5. Detailed Implementation Steps

1. Add task validation.
2. Add preview output for upcoming birthdays.
3. Support `MM-DD` and `YYYY-MM-DD`.
4. Add disabled-task filtering.
5. Add dry-run execution plan objects.
6. Keep real sending blocked for normal contacts.
7. Add tests for date matching and filtering.
8. Run `pytest`.

## 6. Safety Requirements

- Default output is dry-run only.
- No real sending to normal contacts.
- Log every matched and blocked task.

## 7. Testing Requirements

- Test date formats.
- Test invalid dates.
- Test disabled rows.
- Test non-test target remains blocked.
- Run `pytest`.

## 8. Git Branch Name

`feature/birthday-scheduler`

## 9. Commit Message

`Build birthday scheduler dry-run flow`

## 10. Acceptance Criteria

- Scheduler produces clear dry-run plans.
- Invalid tasks are logged but do not crash.
- Tests pass.

## 11. What Not To Do

- Do not start an infinite background loop by default.
- Do not add bulk real sending.
- Do not read WeChat data.

## 12. Final Report Format

Report scheduler behavior, test cases, safety blocks, and next template milestone.
